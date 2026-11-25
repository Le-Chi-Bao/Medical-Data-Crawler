"""Reproducible secure transport demo, using synthetic HTTP bytes and no sockets."""

import http.client
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs

from .api_transport import ESEARCH, APISettings, ProviderBudget, SecureMetadataTransport
from .catalog import AccessDomain, Catalog, Document, Observation, Rendition
from .catalog.discovery import CatalogDiscoveryWriter
from .discovery import DiscoveryError, DiscoveryPermit, DiscoveryRequest
from .operation_policy import OperationPolicyGate, discovery_scope
from .pubmed import PubMedDiscoveryConnector, capture_live_snapshot
from .pubmed_pilot import SEARCH_PROFILES, _authority

NOW = datetime(2026, 11, 25, 8, tzinfo=UTC)
IDS = ("990000002", "990000006")  # Deliberately not descending PMID order.


class SimulatedClock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


class _SocketBytes:
    def __init__(self, payload):
        self.payload = payload

    def makefile(self, mode):
        return BytesIO(self.payload)


class SimulatedPubMedWire:
    """An in-memory HTTP peer. Used only when explicitly injected in offline mode."""

    def __init__(self):
        self.calls = 0

    @contextmanager
    def post(self, host, target, address, user_agent, *, body, deadline, before_send):
        before_send()
        self.calls += 1
        form = parse_qs(body.decode())
        if self.calls in {1, 3}:
            status = 429 if self.calls == 1 else 503
            payload = b""
            extra = b"Retry-After: 1\r\n"
        elif target.endswith("esearch.fcgi"):
            status, extra = 200, b""
            payload = json.dumps(
                {
                    "header": {"type": "esearch", "version": "0.3"},
                    "esearchresult": {"count": "2", "retstart": "0", "retmax": "2", "idlist": IDS},
                }
            ).encode()
        else:
            status, extra = 200, b""
            ids = form["id"][0].split(",")
            payload = json.dumps(
                {
                    "header": {"type": "esummary", "version": "0.3"},
                    "result": {
                        "uids": list(reversed(ids)),
                        **{
                            p: {
                                "uid": p,
                                "title": "Synthetic skin lesion study " + p,
                                "authors": [{"name": "Synthetic Author"}],
                                "fulljournalname": "Fictional Dermatology",
                                "pubdate": "2026 Nov",
                                "pubtype": ["Journal Article"],
                                "articleids": [{"idtype": "doi", "value": "10.99999/demo-" + p}],
                                "abstract": "UNAUTHORIZED_ABSTRACT",
                                "url": "https://unknown.invalid/",
                            }
                            for p in ids
                        },
                    },
                }
            ).encode()
        raw = (
            f"HTTP/1.1 {status} Simulated\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(payload)}\r\n".encode()
            + extra
            + b"\r\n"
            + payload
        )
        with http.client.HTTPResponse(_SocketBytes(raw)) as response:
            response.begin()
            yield response


def demo_transport():
    from ipaddress import ip_address

    permit = DiscoveryPermit(
        "synthetic-approval",
        "secure-demo",
        "melanoma-v1",
        SEARCH_PROFILES["melanoma-v1"],
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 12, 1, tzinfo=UTC),
        allow_discovery=True,
        allow_retention=True,
    )
    authority = _authority(permit)
    gate, timer = OperationPolicyGate(authority), SimulatedClock()
    transport = SecureMetadataTransport(
        permit,
        gate,
        settings=APISettings(enabled=True),
        wire=SimulatedPubMedWire(),
        resolver=lambda _: (ip_address("93.184.215.14"),),
        budget=ProviderBudget(clock=timer, sleeper=timer.sleep),
        clock=timer,
        wall_clock=lambda: NOW,
        sleeper=timer.sleep,
        jitter=lambda: 0.5,
    )
    return permit, authority, timer, transport


def run_demo(output=Path("data/secure-api-demo")):
    permit, authority, timer, transport = demo_transport()
    request = DiscoveryRequest(permit.domain_id, permit.profile_id, permit.query)
    snapshot = capture_live_snapshot(request, permit, transport, limit=2, clock=lambda: NOW)
    assert snapshot.pmids == IDS
    connector = PubMedDiscoveryConnector(
        snapshot,
        cursor_key=b"public-synthetic-demo-cursor-key-0000",
        transport=transport,
        clock=lambda: NOW,
    )
    with Catalog(output / "catalog") as catalog:
        catalog.create_domain(AccessDomain(permit.domain_id))
        scope = catalog.domain(permit.domain_id)
        writer = CatalogDiscoveryWriter(scope, connector)
        first = writer.run(request, permit)
        assert first.report.accepted == 2
        before = scope.list(Observation, limit=1000)
        replay = writer.run(request, permit)
        assert replay.report.accepted == 2 and scope.list(Observation, limit=1000) == before
        blocks = []
        for operation in (
            "fetch_document",
            "store_original",
            "extract_content",
            "export_data",
            "ai_use",
        ):
            try:
                transport.gate.require(
                    permit.id + ":discover_metadata",
                    discovery_scope(permit, operation),
                    NOW,
                )
                raise AssertionError("Full-text rights must be absent")
            except DiscoveryError as error:
                blocks.append(error.code)
        try:
            transport.exchange(ESEARCH + "?api_key=synthetic-secret", {}, max_bytes=256)
            raise AssertionError("An arbitrary URL must fail")
        except DiscoveryError as error:
            assert error.code == "endpoint_denied"
        authority.revoke(permit.id + ":retain_metadata")
        denied = writer.run(request, permit)
        assert denied.report.issues[0].code == "permission_revoked"
        assert scope.list(Rendition) == () and len(scope.list(Document)) == 2
        assert "UNAUTHORIZED_" not in "\n".join(catalog._connection.iterdump())
        catalog.verify()
        result = {
            "integrity": "pass",
            "found": 2,
            "accepted": 2,
            "already_known": 2,
            "rejected": 1,
            "rejection_reasons": ["permission_revoked"],
            "full_text_blocks": blocks,
            "full_text_downloads": 0,
            "network_requests": 0,
            "simulated_attempts": transport.attempts,
            "retries": transport.retries,
            "rate_limit_waits": len(timer.waits),
            "documents": 2,
            "observations": len(before),
            "renditions": 0,
        }
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
