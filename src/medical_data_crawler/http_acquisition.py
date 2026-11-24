"""Opt-in acquisition of one reviewed HTTPS document with an immutable original."""

import http.client
import re
import ssl
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from ipaddress import ip_network
from threading import Lock
from time import monotonic, sleep
from typing import Protocol

from ._https_transport import DirectHTTPSTransport, IPAddress, resolve_host
from .acquisition import AcquisitionResult, DocumentRequest
from .provenance import HTTPAttempt, HTTPTrace, ProvenanceError, ProvenanceStore, document_id
from .source_policy import (
    SourcePolicyError,
    allows_asset_use,
    allows_automated_fetch,
    public_document_host,
    validate_registry,
)
from .storage import Artifact, ArtifactStore, StorageError

_MEDIA_TYPES = {"html": "text/html", "pdf": "application/pdf"}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
_PUBLIC_IPV6 = ip_network("2000::/3")
_SPECIAL_NETWORKS = tuple(
    ip_network(cidr)
    for cidr in (
        "192.0.0.0/24",
        "192.88.99.0/24",
        "2001::/23",
        "2002::/16",
        "3fff::/20",
    )
)


@dataclass(frozen=True)
class HTTPAcquisitionSettings:
    enabled: bool = False
    user_agent: str = "MedicalDataCrawler"
    connect_timeout: float = 5.0
    read_timeout: float = 10.0
    request_timeout: float = 30.0
    max_bytes: int = 16 * 1024**2
    max_redirects: int = 3
    max_retries: int = 2
    min_host_interval: float = 1.0

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("invalid_http_enabled")
        if not isinstance(self.user_agent, str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9.-]{0,63}", self.user_agent
        ):
            raise ValueError("invalid_http_user_agent")
        for name, value, minimum, maximum in (
            ("connect_timeout", self.connect_timeout, 0.01, 120),
            ("read_timeout", self.read_timeout, 0.01, 120),
            ("request_timeout", self.request_timeout, 0.01, 300),
            ("min_host_interval", self.min_host_interval, 0.01, 60),
        ):
            if type(value) not in (int, float) or not minimum <= value <= maximum:
                raise ValueError(f"invalid_http_{name}")
        for name, value, minimum, maximum in (
            ("max_bytes", self.max_bytes, 1, 128 * 1024**2),
            ("max_redirects", self.max_redirects, 0, 5),
            ("max_retries", self.max_retries, 0, 4),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"invalid_http_{name}")


class HTTPTransport(Protocol):
    """Trusted injection point for offline testing with a synthetic response."""

    def get(
        self,
        host: str,
        target: str,
        address: IPAddress,
        user_agent: str,
        *,
        before_send: Callable[[], None],
    ) -> AbstractContextManager[http.client.HTTPResponse]: ...


class _HTTPFailure(Exception):
    def __init__(self, code: str, *, retry: bool = False, delay: float = 0):
        super().__init__(code)
        self.code = code
        self.retry = retry
        self.delay = delay


@contextmanager
def _network_errors() -> Iterator[None]:
    try:
        yield
    except TimeoutError:
        raise _HTTPFailure("http_timeout", retry=True) from None
    except ssl.SSLError:
        raise _HTTPFailure("http_tls_failure") from None
    except OSError:
        raise _HTTPFailure("http_connection_failure", retry=True) from None
    except http.client.HTTPException:
        raise _HTTPFailure("http_incomplete_response", retry=True) from None


def _public_address(address: IPAddress) -> bool:
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and (address.version == 4 or address in _PUBLIC_IPV6)
        and not any(address in network for network in _SPECIAL_NETWORKS)
    )


def _status_failure(response: http.client.HTTPResponse) -> _HTTPFailure:
    status = response.status
    if not 400 <= status <= 599:
        return _HTTPFailure("http_unexpected_status")
    code = "http_4xx" if status < 500 else "http_5xx"
    if status not in _RETRY_STATUSES:
        return _HTTPFailure(code)
    retry_after = response.headers.get_all("Retry-After", [])
    if not retry_after:
        return _HTTPFailure(code, retry=True)
    if len(retry_after) == 1:
        value = retry_after[0].strip()
        try:
            if re.fullmatch(r"[0-9]{1,3}", value):
                delay = int(value)
            else:
                at = parsedate_to_datetime(value)
                if at.tzinfo is None:
                    return _HTTPFailure(code)
                delay = max(0, (at - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return _HTTPFailure(code)
        if delay <= 30:
            return _HTTPFailure(code, retry=True, delay=delay)
    return _HTTPFailure(code)


class _Body:
    """A bounded stream. Raise before ArtifactStore publishes a truncated original."""

    def __init__(self, response: http.client.HTTPResponse, length: int, close: Callable[[], None]):
        self.response = response
        self.remaining = length
        self.close = close

    def read(self, size: int) -> bytes:
        if self.remaining == 0:
            with _network_errors():
                self.close()
            return b""
        size = min(size, self.remaining)
        with _network_errors():
            chunk = self.response.read(size)
        if not chunk or len(chunk) > size:
            raise _HTTPFailure("http_incomplete_response", retry=True)
        self.remaining -= len(chunk)
        return chunk


def _response_length(response: http.client.HTTPResponse, media_type: str, limit: int) -> int:
    headers = response.headers
    encoding = headers.get_all("Content-Encoding", [])
    if encoding and (len(encoding) != 1 or encoding[0].strip().lower() != "identity"):
        raise _HTTPFailure("http_unexpected_content_encoding")
    types = headers.get_all("Content-Type", [])
    if len(types) != 1 or types[0].split(";", 1)[0].strip().lower() != media_type:
        raise _HTTPFailure("http_unsupported_media_type")
    lengths = headers.get_all("Content-Length", [])
    if (
        headers.defects
        or "Transfer-Encoding" in headers
        or "Content-Range" in headers
        or len(lengths) != 1
        or not re.fullmatch(r"[0-9]+", lengths[0].strip(" \t"))
    ):
        raise _HTTPFailure("http_unsupported_framing")
    length = lengths[0].strip(" \t")
    if len(length) > 10:
        raise _HTTPFailure("http_response_too_large")
    size = int(length)
    if size > limit:
        raise _HTTPFailure("http_response_too_large")
    if size == 0:
        raise _HTTPFailure("http_incomplete_response")
    return size


@dataclass(frozen=True)
class _Redirect:
    location: str


class _HostThrottle:
    def __init__(self):
        self.lock = Lock()
        self.next_start = 0.0


_DEFAULT_HTTP_SETTINGS = HTTPAcquisitionSettings()


class HTTPDocumentAdapter:
    """GET explicit registry URLs via the direct transport, disabled by default."""

    def __init__(
        self,
        artifacts: ArtifactStore,
        provenance: ProvenanceStore,
        registry: object,
        *,
        settings: HTTPAcquisitionSettings = _DEFAULT_HTTP_SETTINGS,
        resolver: Callable[[str], tuple[IPAddress, ...]] = resolve_host,
        transport: HTTPTransport | None = None,
    ):
        if provenance.artifacts is not artifacts:
            raise ValueError("Acquisition and provenance must use the same ArtifactStore")
        self.artifacts = artifacts
        self.provenance = provenance
        self.settings = settings
        self._registry = deepcopy(registry)
        try:
            validate_registry(self._registry)
        except SourcePolicyError:
            self._sources = {}
        else:
            self._sources = {
                source["candidate_url"]: source for source in self._registry["sources"]
            }
        self._hosts = {source["domain"]: _HostThrottle() for source in self._sources.values()}
        self._resolver = resolver
        self._transport = (
            transport
            if transport is not None
            else DirectHTTPSTransport(
                connect_timeout=settings.connect_timeout,
                read_timeout=settings.read_timeout,
                request_timeout=settings.request_timeout,
            )
        )

    def acquire(self, request: DocumentRequest) -> AcquisitionResult:
        acquired_at = datetime.now(UTC)
        try:
            identity = document_id(request.source_id, request.logical_key)
        except ProvenanceError:
            return AcquisitionResult(
                request, None, acquired_at, None, None, None, ("http_invalid_identity",)
            )
        try:
            public_document_host(request.locator)
        except SourcePolicyError:
            return AcquisitionResult(
                request, identity, acquired_at, None, None, None, ("http_invalid_url",)
            )
        source = self._sources.get(request.locator)
        if source is None or source["source_id"] != request.source_id:
            error = "http_authorization_denied" if self.settings.enabled else "http_disabled"
            return AcquisitionResult(request, identity, acquired_at, None, None, None, (error,))

        attempts: list[HTTPAttempt] = []
        artifact = None
        media_type = None
        extraction_types = None
        outcome = "accepted"
        try:
            if not self.settings.enabled:
                raise _HTTPFailure("http_disabled")
            if request.path is not None:
                raise _HTTPFailure("http_invalid_url")
            artifact, final_source = self._download(source, attempts)
            media_type = _MEDIA_TYPES[final_source["document_type"]]
            extraction_types = self._extraction_types(source, final_source, media_type)
        except _HTTPFailure as error:
            outcome = error.code
        errors = () if outcome == "accepted" else (outcome,)
        event_id = None
        try:
            event_id = self.provenance.record(
                source_id=request.source_id,
                logical_key=request.logical_key,
                locator=request.locator,
                acquired_at=acquired_at,
                checksum=artifact.sha256 if artifact else None,
                error_code=self._event_error(outcome),
                http=HTTPTrace(self.settings.user_agent, outcome, tuple(attempts)),
            )
        except ProvenanceError:
            errors += ("http_provenance_failure",)
        return AcquisitionResult(
            request, identity, acquired_at, media_type, artifact, event_id, errors, extraction_types
        )

    @staticmethod
    def _event_error(outcome: str) -> str | None:
        if outcome == "accepted":
            return None
        if outcome in {"http_invalid_url", "http_authorization_denied", "http_disabled"}:
            return "invalid_input"
        return "read_error"

    def _allowed(self, source: dict) -> bool:
        # Policy validation includes both original_bytes grants, embedded assets,
        # Terms of Service, robots evidence and the current review window.
        return allows_automated_fetch(
            self._registry,
            source["source_id"],
            source["candidate_url"],
            user_agent=self.settings.user_agent,
            at=datetime.now(UTC),
        )

    def _require_allowed(self, source: dict) -> None:
        if not self._allowed(source):
            raise _HTTPFailure("http_authorization_denied")

    def _extraction_types(self, initial: dict, final: dict, media_type: str) -> frozenset[str]:
        at = datetime.now(UTC)
        asset = f"{final['document_type']}_text"
        allowed = all(
            allows_asset_use(
                self._registry,
                source["source_id"],
                source["candidate_url"],
                asset=asset,
                action=action,
                at=at,
            )
            for source in (initial, final)
            for action in ("read", "internal_storage")
        )
        return frozenset({media_type}) if allowed else frozenset()

    def _download(self, source: dict, attempts: list[HTTPAttempt]) -> tuple[Artifact, dict]:
        visited = {source["candidate_url"]}
        retries = 0
        while True:
            try:
                result = self._exchange(source, attempts)
            except _HTTPFailure as error:
                if not error.retry or retries >= self.settings.max_retries:
                    raise
                sleep(max(0.5 * 2**retries, error.delay))
                retries += 1
                continue
            if isinstance(result, Artifact):
                return result, source
            if len(visited) > self.settings.max_redirects:
                raise _HTTPFailure("http_redirect_rejected")
            source = self._redirect_target(source, result.location, visited)
            visited.add(source["candidate_url"])

    def _redirect_target(self, source: dict, location: str, visited: set[str]) -> dict:
        if location.startswith("/") and not location.startswith("//"):
            location = f"https://{source['domain']}{location}"
        try:
            public_document_host(location)
        except SourcePolicyError:
            raise _HTTPFailure("http_redirect_rejected") from None
        target = self._sources.get(location)
        if (
            target is None
            or location in visited
            or target["document_type"] != source["document_type"]
            or not self._allowed(target)
        ):
            raise _HTTPFailure("http_redirect_rejected")
        return target

    def _exchange(self, source: dict, attempts: list[HTTPAttempt]) -> Artifact | _Redirect:
        host, locator = source["domain"], source["candidate_url"]
        throttle = self._hosts[host]
        with throttle.lock:
            wait = throttle.next_start - monotonic()
            if wait > 0:
                sleep(wait)
            self._require_allowed(source)
            attempted_at = datetime.now(UTC).isoformat()
            status = None
            outcome = "accepted"
            try:
                with _network_errors():
                    addresses = self._resolver(host)
                    if not addresses:
                        raise _HTTPFailure("http_connection_failure", retry=True)
                    if not all(_public_address(address) for address in addresses):
                        raise _HTTPFailure("http_unsafe_address")
                    self._require_allowed(source)
                    target = locator.removeprefix(f"https://{host}") or "/"
                    with ExitStack() as connection:
                        response = connection.enter_context(
                            self._transport.get(
                                host,
                                target,
                                addresses[0],
                                self.settings.user_agent,
                                before_send=lambda: self._require_allowed(source),
                            )
                        )
                        status = response.status
                        if status in _REDIRECT_STATUSES:
                            locations = response.headers.get_all("Location", [])
                            if len(locations) != 1 or response.headers.defects:
                                raise _HTTPFailure("http_redirect_rejected")
                            outcome = "redirect"
                            return _Redirect(locations[0])
                        if 300 <= status < 400:
                            raise _HTTPFailure("http_redirect_rejected")
                        if status != 200:
                            raise _status_failure(response)
                        media_type = _MEDIA_TYPES[source["document_type"]]
                        length = _response_length(response, media_type, self.settings.max_bytes)
                        # Finish network cleanup before put() can commit its pending file.
                        return self.artifacts.put(_Body(response, length, connection.close))
            except StorageError:
                outcome = "http_storage_failure"
                raise _HTTPFailure(outcome) from None
            except _HTTPFailure as error:
                outcome = error.code
                raise
            finally:
                throttle.next_start = monotonic() + self.settings.min_host_interval
                attempts.append(
                    HTTPAttempt(source["source_id"], locator, attempted_at, status, outcome)
                )
