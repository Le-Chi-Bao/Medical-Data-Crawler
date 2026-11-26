"""Single-worker PMC XML transport using the existing pinned-IP TLS wire."""

import http.client
import re
import ssl
from time import monotonic
from urllib.parse import urlencode

from ._https_transport import DirectHTTPSTransport
from .api_transport import (
    _LIVE_EXCHANGE_LOCK,
    _PROVIDER_BUDGET,
    _bounded_resolve,
    _headers,
    _single_process_lease,
)
from .discovery import DiscoveryError
from .http_acquisition import _public_address
from .jats import MAX_XML_BYTES

ENDPOINT = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
HOST = "pmc.ncbi.nlm.nih.gov"


def validate_pmcid(value):
    if not isinstance(value, str) or re.fullmatch(r"PMC[1-9][0-9]{0,11}", value) is None:
        raise DiscoveryError("invalid_pmcid")
    return value


class PMCTransport:
    is_live = True

    def __init__(self, *, enabled=False, exclusive_provider_ip=False, wire=None, resolver=None):
        self.enabled = enabled
        self.exclusive_provider_ip = exclusive_provider_ip
        self.wire = wire or DirectHTTPSTransport(
            connect_timeout=5, read_timeout=10, request_timeout=30
        )
        self.resolver = resolver
        _PROVIDER_BUDGET.register(1)

    def fetch(self, pmcid, authorize, *, endpoint=ENDPOINT):
        validate_pmcid(pmcid)
        if endpoint != ENDPOINT:
            raise DiscoveryError("endpoint_denied")
        if not self.enabled:
            raise DiscoveryError("network_disabled")
        if not self.exclusive_provider_ip:
            raise DiscoveryError("shared_ip_uncoordinated")
        authorize()
        _single_process_lease()
        if not _LIVE_EXCHANGE_LOCK.acquire(timeout=30):
            raise DiscoveryError("deadline_exceeded")
        try:
            return self._fetch(pmcid, authorize)
        except ssl.SSLError:
            raise DiscoveryError("tls_failure") from None
        except TimeoutError:
            raise DiscoveryError("response_timeout") from None
        except (OSError, http.client.HTTPException):
            raise DiscoveryError("connection_interrupted") from None
        finally:
            _LIVE_EXCHANGE_LOCK.release()

    def _fetch(self, pmcid, authorize):
        deadline = monotonic() + 30
        addresses = self.resolver(HOST) if self.resolver else _bounded_resolve(HOST, 5)
        if not addresses or not all(_public_address(a) for a in addresses):
            raise DiscoveryError("unsafe_address")
        if monotonic() >= deadline:
            raise DiscoveryError("deadline_exceeded")

        def before_send():
            _PROVIDER_BUDGET.wait(deadline)
            authorize()

        body = urlencode(
            {
                "verb": "GetRecord",
                "metadataPrefix": "pmc",
                "identifier": "oai:pubmedcentral.nih.gov:" + pmcid[3:],
            }
        ).encode("ascii")
        with self.wire.post(
            HOST,
            "/api/oai/v1/mh/",
            addresses[0],
            "MedicalDataCrawler",
            body=body,
            deadline=deadline,
            before_send=before_send,
            accept="application/xml",
            accept_encoding="identity",
        ) as response:
            _headers(response)
            if 300 <= response.status < 400:
                raise DiscoveryError("redirect_denied")
            # No automatic retries: a failed pilot requires renewed operator approval.
            if response.status in {429, 503}:
                raise DiscoveryError("rate_limited")
            if response.status != 200:
                raise DiscoveryError("http_status_denied")
            mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if mime not in {"application/xml", "text/xml"}:
                raise DiscoveryError("content_type_denied")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise DiscoveryError("encoding_denied")
            length = response.headers.get("Content-Length")
            if length is not None and (
                not length.isdecimal() or len(length) > 9 or int(length) > MAX_XML_BYTES
            ):
                raise DiscoveryError("xml_size_denied")
            payload = bytearray()
            while True:
                if monotonic() >= deadline:
                    raise DiscoveryError("deadline_exceeded")
                chunk = response.read1(min(8192, MAX_XML_BYTES - len(payload) + 1))
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > MAX_XML_BYTES:
                    raise DiscoveryError("xml_size_denied")
            if length is not None and len(payload) != int(length):
                raise DiscoveryError("incomplete_response")
            authorize()
            return bytes(payload)
