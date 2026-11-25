"""Bounded, opt-in NCBI metadata transport. No response-derived destinations."""

import http.client
import math
import os
import queue
import random
import re
import ssl
import tempfile
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import BoundedSemaphore, Lock, Thread
from time import monotonic, sleep
from urllib.parse import urlencode

from ._https_transport import DirectHTTPSTransport, resolve_host
from .discovery import (
    MAX_RESPONSE_BYTES,
    DiscoveryError,
    DiscoveryPermit,
    DiscoveryRequest,
    SearchSnapshot,
)
from .discovery import (
    authorize as authorize_discovery,
)
from .http_acquisition import _public_address
from .operation_policy import OperationPolicyGate, discovery_scope

HOST = "eutils.ncbi.nlm.nih.gov"
ESEARCH = f"https://{HOST}/entrez/eutils/esearch.fcgi"
ESUMMARY = f"https://{HOST}/entrez/eutils/esummary.fcgi"
_DNS_SLOTS = BoundedSemaphore(4)
_LIVE_EXCHANGE_LOCK = Lock()


@dataclass(frozen=True)
class APISettings:
    enabled: bool = False
    workers: int = 1
    exclusive_provider_ip: bool = False
    connect_timeout: float = 5
    read_timeout: float = 10
    request_timeout: float = 20
    total_timeout: float = 60
    max_wire_bytes: int = MAX_RESPONSE_BYTES
    max_retries: int = 2
    requests_per_second: float = 3
    tool: str = "MedicalDataCrawler"
    email: str | None = field(default=None, repr=False)
    api_key: str | None = field(default=None, repr=False)

    def __post_init__(self):
        if (
            type(self.enabled) is not bool
            or type(self.exclusive_provider_ip) is not bool
            or type(self.workers) is not int
            or self.workers != 1
            or type(self.max_retries) is not int
            or not 0 <= self.max_retries <= 4
            or type(self.max_wire_bytes) is not int
            or not 1 <= self.max_wire_bytes <= MAX_RESPONSE_BYTES
            or type(self.tool) is not str
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,63}", self.tool)
        ):
            raise DiscoveryError("invalid_configuration")
        for value in (
            self.connect_timeout,
            self.read_timeout,
            self.request_timeout,
            self.total_timeout,
            self.requests_per_second,
        ):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 300:
                raise DiscoveryError("invalid_configuration")
        if self.requests_per_second > (10 if self.api_key else 3):
            raise DiscoveryError("invalid_configuration")
        if self.api_key is not None and (
            type(self.api_key) is not str
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", self.api_key)
        ):
            raise DiscoveryError("invalid_configuration")
        if self.email is not None and (
            type(self.email) is not str
            or not re.fullmatch(
                r"[A-Za-z0-9_.+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}", self.email
            )
        ):
            raise DiscoveryError("invalid_configuration")


class ProviderBudget:
    """One conservative process-wide provider budget, across all instances/keys.

    The lowest registered ceiling wins until process restart. No bursts.
    Live mode additionally takes an OS lease and requires exclusive egress.
    """

    def __init__(self, *, clock=monotonic, sleeper=sleep):
        self.clock, self.sleeper = clock, sleeper
        self._lock = Lock()
        self._ceiling = 10.0
        self._last: float | None = None
        self._blocked_until = 0.0

    def register(self, rate):
        with self._lock:
            self._ceiling = min(self._ceiling, rate)

    def defer(self, seconds):
        with self._lock:
            self._blocked_until = max(self._blocked_until, self.clock() + seconds)

    def wait(self, deadline):
        if not self._lock.acquire(timeout=max(0, deadline - self.clock())):
            raise DiscoveryError("deadline_exceeded")
        try:
            due = max(
                self._blocked_until,
                self._last + 1 / self._ceiling if self._last is not None else self.clock(),
            )
            delay = max(0, due - self.clock())
            if self.clock() + delay >= deadline:
                raise DiscoveryError("deadline_exceeded")
            if delay:
                self.sleeper(delay)
            if self.clock() >= deadline:
                raise DiscoveryError("deadline_exceeded")
            self._last = self.clock()
        finally:
            self._lock.release()


_PROVIDER_BUDGET = ProviderBudget()
_LEASE_LOCK = Lock()
_LEASE = None
_LEASE_PID = None


def _single_process_lease():
    global _LEASE, _LEASE_PID
    with _LEASE_LOCK:
        if _LEASE is not None:
            if _LEASE_PID != os.getpid():
                raise DiscoveryError("worker_conflict")
            return
        stream = None
        try:
            path = Path(tempfile.gettempdir()) / "medical-data-crawler-ncbi-worker.lock"
            stream = path.open("a+b")
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                if not stream.read(1):
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if stream is not None:
                stream.close()
            raise DiscoveryError("worker_conflict") from None
        _LEASE, _LEASE_PID = stream, os.getpid()


def _bounded_resolve(host, timeout):
    # getaddrinfo has no portable timeout. A bounded number of daemon threads
    # prevents blocked system DNS from defeating the caller's total deadline.
    if not _DNS_SLOTS.acquire(blocking=False):
        raise DiscoveryError("dns_unavailable")
    results = queue.Queue(maxsize=1)

    def run():
        try:
            results.put(resolve_host(host))
        except Exception:
            results.put(None)
        finally:
            _DNS_SLOTS.release()

    Thread(target=run, daemon=True).start()
    try:
        answer = results.get(timeout=timeout)
    except queue.Empty:
        raise TimeoutError from None
    if not answer:
        raise DiscoveryError("dns_unavailable")
    return answer


def _parameters(endpoint, parameters, query):
    if type(endpoint) is not str or endpoint not in {ESEARCH, ESUMMARY}:
        raise DiscoveryError("endpoint_denied")
    if type(parameters) is not dict or any(
        type(k) is not str or type(v) is not str for k, v in parameters.items()
    ):
        raise DiscoveryError("parameters_denied")
    constants = {"db": "pubmed", "retmode": "json"}
    if endpoint == ESEARCH:
        constants["sort"] = "pub_date"
        allowed = {*constants, "term", "retstart", "retmax"}
        if parameters.get("term") != query:
            raise DiscoveryError("parameters_denied")
        for name, lower, upper in (("retstart", 0, 9999), ("retmax", 1, 100)):
            value = parameters.get(name, "")
            if not re.fullmatch(r"0|[1-9][0-9]{0,4}", value) or not lower <= int(value) <= upper:
                raise DiscoveryError("parameters_denied")
        if int(parameters["retstart"]) + int(parameters["retmax"]) > 10000:
            raise DiscoveryError("retrieval_window_exceeded")
    else:
        constants["version"] = "2.0"
        allowed = {*constants, "id"}
        ids = parameters.get("id", "").split(",")
        if (
            not 1 <= len(ids) <= 100
            or len(set(ids)) != len(ids)
            or any(not re.fullmatch(r"[1-9][0-9]{0,11}", value) for value in ids)
        ):
            raise DiscoveryError("parameters_denied")
    if set(parameters) != allowed or any(parameters.get(k) != v for k, v in constants.items()):
        raise DiscoveryError("parameters_denied")


def _headers(response):
    headers = response.headers
    if headers.defects or len(headers) > 64:
        raise DiscoveryError("invalid_headers")
    size = 0
    for name, value in headers.items():
        size += len(name) + len(value)
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) or any(
            ord(c) < 32 and c != "\t" or ord(c) == 127 for c in value
        ):
            raise DiscoveryError("invalid_headers")
    if size > 16384:
        raise DiscoveryError("invalid_headers")
    for name in (
        "Content-Type",
        "Content-Encoding",
        "Content-Length",
        "Transfer-Encoding",
        "Retry-After",
    ):
        if len(headers.get_all(name, [])) > 1:
            raise DiscoveryError("invalid_headers")
    transfer = headers.get("Transfer-Encoding")
    if (
        transfer is not None
        and transfer.lower().strip() != "chunked"
        or transfer is not None
        and "Content-Length" in headers
        or "Content-Range" in headers
    ):
        raise DiscoveryError("invalid_headers")


_DEFAULT_API_SETTINGS = APISettings()


class SecureMetadataTransport:
    """MetadataTransport implementation. All injected components are operator-trusted."""

    def __init__(
        self,
        permit: DiscoveryPermit,
        gate: OperationPolicyGate,
        *,
        settings=_DEFAULT_API_SETTINGS,
        wire=None,
        resolver=None,
        budget=None,
        clock=monotonic,
        wall_clock=lambda: datetime.now(UTC),
        sleeper=sleep,
        jitter=lambda: random.uniform(0.5, 1.0),
    ):
        self.settings, self.permit, self.gate = settings, permit, gate
        self._validation_snapshot = SearchSnapshot(
            "transport-validation",
            permit.profile_id,
            permit.query,
            (),
        )
        self._inventory: tuple[str, ...] | None = None
        self.clock, self.wall_clock, self.sleeper, self.jitter = clock, wall_clock, sleeper, jitter
        self.is_live = wire is None
        self._wire = (
            wire
            if wire is not None
            else DirectHTTPSTransport(
                connect_timeout=settings.connect_timeout,
                read_timeout=settings.read_timeout,
                request_timeout=settings.request_timeout,
            )
        )
        self._resolver = resolver
        self._budget = budget if budget is not None else _PROVIDER_BUDGET
        self._budget.register(settings.requests_per_second)
        self.attempts = 0
        self.retries = 0

    def authorize(self, permit=None):
        if permit is not None and discovery_scope(permit) != discovery_scope(self.permit):
            raise DiscoveryError("permission_denied")
        if self.permit.allow_discovery is not True or self.permit.allow_retention is not True:
            raise DiscoveryError("permission_denied")
        self.gate.discovery(self.permit, self.wall_clock())
        authorize_discovery(
            DiscoveryRequest(self.permit.domain_id, self.permit.profile_id, self.permit.query),
            self.permit,
            self._validation_snapshot,
            self.wall_clock(),
        )

    def bind_snapshot(self, snapshot: SearchSnapshot):
        """Trusted connector/capture boundary; never bind from submitted parameters."""
        self.authorize()
        if (
            type(snapshot) is not SearchSnapshot
            or snapshot.profile_id != self.permit.profile_id
            or snapshot.query != self.permit.query
            or self.is_live
            and snapshot.sort != "provider-pub-date"
            or self._inventory is not None
            and self._inventory != snapshot.pmids
        ):
            raise DiscoveryError("snapshot_binding_mismatch")
        self._inventory = snapshot.pmids

    def _deadline(self, deadline):
        if self.clock() >= deadline:
            raise DiscoveryError("deadline_exceeded")

    def exchange(self, endpoint, parameters, *, max_bytes):
        # Copy request data before any wait/callback: callers cannot mutate validation away.
        locked = False
        try:
            if type(parameters) is not dict:
                raise DiscoveryError("parameters_denied")
            deadline = self.clock() + self.settings.total_timeout
            if self.is_live:
                locked = _LIVE_EXCHANGE_LOCK.acquire(timeout=self.settings.total_timeout)
                if not locked:
                    raise DiscoveryError("deadline_exceeded")
            return self._exchange(endpoint, dict(parameters), max_bytes, deadline)
        except DiscoveryError:
            raise
        except Exception:
            raise DiscoveryError("transport_failure") from None
        finally:
            if locked:
                _LIVE_EXCHANGE_LOCK.release()

    def _exchange(self, endpoint, parameters, max_bytes, deadline):
        if not self.settings.enabled:
            raise DiscoveryError("network_disabled")
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_RESPONSE_BYTES:
            raise DiscoveryError("invalid_configuration")
        _parameters(endpoint, parameters, self.permit.query)
        self.authorize()
        if endpoint == ESUMMARY:
            if self._inventory is None:
                raise DiscoveryError("snapshot_required")
            if not set(parameters["id"].split(",")) <= set(self._inventory):
                raise DiscoveryError("parameters_denied")
        if self.is_live:
            if not self.settings.exclusive_provider_ip:
                raise DiscoveryError("shared_ip_uncoordinated")
            _single_process_lease()
        # NCBI accepts form POST. Neither key nor email ever appears in the target URL.
        form = {**parameters, "tool": self.settings.tool}
        if self.settings.email:
            form["email"] = self.settings.email
        if self.settings.api_key:
            form["api_key"] = self.settings.api_key
        body = urlencode(form).encode("ascii")
        target = endpoint.removeprefix(f"https://{HOST}")
        for attempt in range(self.settings.max_retries + 1):
            delay = 0
            payload = None
            try:
                self._deadline(deadline)
                self.authorize()
                self._deadline(deadline)
                addresses = (
                    self._resolver(HOST)
                    if self._resolver is not None
                    else _bounded_resolve(
                        HOST, min(self.settings.connect_timeout, deadline - self.clock())
                    )
                )
                self._deadline(deadline)
                if not addresses or not all(_public_address(a) for a in addresses):
                    raise DiscoveryError("unsafe_address")

                request_deadline = min(deadline, self.clock() + self.settings.request_timeout)

                def before_send(request_deadline=request_deadline):
                    self._budget.wait(request_deadline)
                    self._deadline(request_deadline)
                    self.authorize()

                self.authorize()
                self.attempts += 1
                with self._wire.post(
                    HOST,
                    target,
                    addresses[0],
                    self.settings.tool,
                    body=body,
                    deadline=request_deadline,
                    before_send=before_send,
                ) as response:
                    self._deadline(request_deadline)
                    _headers(response)
                    if 300 <= response.status < 400:
                        raise DiscoveryError("redirect_denied")
                    if response.status in {429, 500, 502, 503, 504}:
                        code = "rate_limited" if response.status == 429 else "provider_unavailable"
                        delay = self._retry_after(response.headers.get("Retry-After"))
                        self._budget.defer(delay)
                    elif response.status != 200:
                        raise DiscoveryError("http_status_denied")
                    else:
                        payload = self._read(response, max_bytes, request_deadline)
                if payload is not None:
                    self._deadline(deadline)
                    self.authorize()
                    return payload
            except ssl.SSLError:
                raise DiscoveryError("tls_failure") from None
            except TimeoutError:
                self._deadline(deadline)
                code = "response_timeout"
            except (OSError, http.client.HTTPException):
                code = "connection_interrupted"
            self._deadline(deadline)
            if attempt == self.settings.max_retries:
                raise DiscoveryError(code)
            delay = max(delay, min(8.0, 0.5 * 2**attempt) + min(1.0, max(0, self.jitter())))
            if self.clock() + delay >= deadline:
                raise DiscoveryError("deadline_exceeded")
            self.authorize()
            self.retries += 1
            self.sleeper(delay)
        raise DiscoveryError("transport_failure")

    def _retry_after(self, value):
        if value is None:
            return 0
        try:
            if re.fullmatch(r"[0-9]{1,9}", value.strip()):
                return int(value)
            at = parsedate_to_datetime(value)
            if at.tzinfo is None:
                raise ValueError
            return max(0, (at - self.wall_clock()).total_seconds())
        except (ValueError, TypeError, OverflowError):
            raise DiscoveryError("invalid_retry_after") from None

    def _read(self, response, limit, deadline):
        content_type = response.headers.get("Content-Type", "")
        if not re.fullmatch(r"application/json(?:\s*;\s*charset=(?:utf-8|UTF-8))?", content_type):
            raise DiscoveryError("content_type_denied")
        encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
        if encoding not in {"identity", "gzip"}:
            raise DiscoveryError("encoding_denied")
        raw_length = response.headers.get("Content-Length")
        length = None
        if raw_length is not None:
            if not re.fullmatch(r"[0-9]{1,9}", raw_length.strip()):
                raise DiscoveryError("invalid_headers")
            length = int(raw_length)
            if length > self.settings.max_wire_bytes:
                raise DiscoveryError("response_too_large")
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
        output = bytearray()
        received = 0
        while True:
            self._deadline(deadline)
            chunk = response.read1(min(8192, self.settings.max_wire_bytes - received + 1))
            self._deadline(deadline)
            if not chunk:
                break
            received += len(chunk)
            if received > self.settings.max_wire_bytes:
                raise DiscoveryError("response_too_large")
            if decoder:
                try:
                    chunk = decoder.decompress(chunk, limit - len(output) + 1)
                except zlib.error:
                    raise DiscoveryError("invalid_compression") from None
                if decoder.unconsumed_tail or decoder.unused_data:
                    raise DiscoveryError("invalid_compression")
            output.extend(chunk)
            if len(output) > limit:
                raise DiscoveryError("response_too_large")
        if length is not None and received != length:
            raise http.client.IncompleteRead(b"")
        if not output or decoder is not None and not decoder.eof:
            raise DiscoveryError("invalid_compression" if decoder else "invalid_payload")
        return bytes(output)
