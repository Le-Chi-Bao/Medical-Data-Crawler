import gzip
import http.client
import ssl
from dataclasses import replace
from datetime import timedelta
from email.utils import format_datetime
from ipaddress import ip_address
from threading import BoundedSemaphore, Event

import pytest
from secure_api_helpers import response, setup_transport

from medical_data_crawler import api_transport
from medical_data_crawler.api_transport import (
    ESEARCH,
    ESUMMARY,
    APISettings,
    ProviderBudget,
    SecureMetadataTransport,
)
from medical_data_crawler.discovery import DiscoveryError
from medical_data_crawler.operation_policy import OperationPolicyGate
from medical_data_crawler.secure_api_demo import NOW, SimulatedClock, demo_transport


def exchange(transport, params, endpoint=ESEARCH, limit=1024):
    return transport.exchange(endpoint, params, max_bytes=limit)


def test_default_disabled_no_dns_and_no_key_required():
    transport, wire, _, _, params = setup_transport(settings=APISettings())
    with pytest.raises(DiscoveryError, match="^network_disabled$"):
        exchange(transport, params)
    assert wire.calls == []
    transport, _, _, _, params = setup_transport()
    assert exchange(transport, params) == b"{}"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        "https://unknown.example/",
        "https://127.0.0.1/",
        ESEARCH + "?db=pubmed",
        ESEARCH.replace("esearch", "efetch"),
        ESEARCH.replace("https://", "https://user@"),
        ESEARCH.replace(".gov/", ".gov:443/"),
        ESEARCH + "#fragment",
    ],
)
def test_endpoint_allowlist(endpoint):
    transport, wire, _, _, params = setup_transport()
    with pytest.raises(DiscoveryError, match="^endpoint_denied$"):
        exchange(transport, params, endpoint)
    assert not wire.calls


@pytest.mark.parametrize(
    "changes",
    [
        {"api_key": "MUST_NOT_LEAK"},
        {"email": "hidden@example.invalid"},
        {"url": "https://x/"},
        {"db": "pmc"},
        {"retmode": "xml"},
        {"term": "unapproved"},
        {"sort": "relevance"},
        {"retstart": "-1"},
        {"retstart": "00"},
        {"retmax": "101"},
        {"retmax": "0"},
        {"retmax": 2},
        {"retmax": "2\r\nX: secret"},
        {"tool": "request-created"},
    ],
)
def test_query_allowlist(changes):
    transport, wire, _, _, params = setup_transport()
    with pytest.raises(DiscoveryError, match="^parameters_denied$"):
        exchange(transport, {**params, **changes})
    assert not wire.calls


@pytest.mark.parametrize("ids", ["0", "01", "1,1", "abc", "1,https://x", ",1", "1,"])
def test_summary_parameters(ids):
    transport, wire, _, _, _ = setup_transport()
    with pytest.raises(DiscoveryError, match="^parameters_denied$"):
        exchange(
            transport, {"db": "pubmed", "retmode": "json", "id": ids, "version": "2.0"}, ESUMMARY
        )
    assert not wire.calls


@pytest.mark.parametrize(
    "location",
    ["https://unknown.example/x", "https://127.0.0.1/", "https://169.254.169.254/", ESEARCH],
)
def test_no_redirects_or_credential_forwarding(location):
    transport, wire, _, _, params = setup_transport(
        response(status=302, headers=[("Location", location)])
    )
    with pytest.raises(DiscoveryError, match="^redirect_denied$"):
        exchange(transport, params)
    assert len(wire.calls) == 1


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.1.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
        "192.0.0.8",
        "2002::1",
    ],
)
def test_private_special_and_mixed_dns_rejected(address):
    transport, wire, _, _, params = setup_transport(
        resolver=lambda _: (ip_address("93.184.215.14"), ip_address(address)),
    )
    with pytest.raises(DiscoveryError, match="^unsafe_address$"):
        exchange(transport, params)
    assert not wire.calls


def test_dns_rebinding_on_retry_is_rejected():
    answers = iter([(ip_address("93.184.215.14"),), (ip_address("127.0.0.1"),)])
    transport, wire, _, _, params = setup_transport(
        response(status=503),
        resolver=lambda _: next(answers),
    )
    with pytest.raises(DiscoveryError, match="^unsafe_address$"):
        exchange(transport, params)
    assert len(wire.calls) == 1


def test_summary_cannot_escape_pinned_inventory():
    from medical_data_crawler.discovery import SearchSnapshot

    transport, wire, _, _, _ = setup_transport()
    params = {"db": "pubmed", "retmode": "json", "version": "2.0", "id": "1"}
    with pytest.raises(DiscoveryError, match="^snapshot_required$"):
        exchange(transport, params, ESUMMARY)
    transport.bind_snapshot(
        SearchSnapshot(
            "pinned",
            transport.permit.profile_id,
            transport.permit.query,
            ("2",),
        )
    )
    with pytest.raises(DiscoveryError, match="^parameters_denied$"):
        exchange(transport, params, ESUMMARY)
    assert not wire.calls


def test_request_deadline_independent_of_total_deadline():
    transport, wire, timer, _, params = setup_transport(
        settings=APISettings(enabled=True, request_timeout=1, total_timeout=60),
    )
    wire.on_open = lambda: timer.sleep(2)
    with pytest.raises(DiscoveryError, match="^deadline_exceeded$"):
        exchange(transport, params)
    assert len(wire.calls) == 1 and timer.now == 2


def test_system_dns_deadline_and_bounded_resolver_threads(monkeypatch):
    released, finished = Event(), Event()
    monkeypatch.setattr(api_transport, "_DNS_SLOTS", BoundedSemaphore(1))

    def blocked_resolve(_):
        try:
            released.wait()
            return (ip_address("93.184.215.14"),)
        finally:
            finished.set()

    monkeypatch.setattr(api_transport, "resolve_host", blocked_resolve)
    try:
        with pytest.raises(TimeoutError):
            api_transport._bounded_resolve(api_transport.HOST, 0.01)
        with pytest.raises(DiscoveryError, match="^dns_unavailable$"):
            api_transport._bounded_resolve(api_transport.HOST, 0.01)
    finally:
        released.set()
        assert finished.wait(5)


@pytest.mark.parametrize(
    "error",
    [
        ssl.SSLCertVerificationError("invalid cert SECRET"),
        ssl.SSLCertVerificationError("hostname mismatch SECRET"),
    ],
)
def test_tls_failures_are_terminal_and_sanitized(error, caplog):
    transport, wire, _, _, params = setup_transport(error)
    with pytest.raises(DiscoveryError, match="^tls_failure$") as caught:
        exchange(transport, params)
    assert "SECRET" not in str(caught.value) + caplog.text and len(wire.calls) == 1


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Length", "2")],
        [("Content-Length", "-1")],
        [("Transfer-Encoding", "chunked")],
        [("Content-Encoding", "gzip"), ("Content-Encoding", "identity")],
        [("Content-Type", "text/html")],
        [("Content-Range", "bytes 0-1/2")],
        [("X-Invalid", "foo\r\n folded")],
        [("Bad Header", "value")],
    ],
)
def test_malformed_headers(headers):
    transport, _, _, _, params = setup_transport(response(headers=headers))
    with pytest.raises(DiscoveryError):
        exchange(transport, params)


def test_content_type_and_encoding_and_gzip_budget():
    for raw, code in [
        (response().replace(b"application/json", b"text/html"), "content_type_denied"),
        (response(headers=[("Content-Encoding", "br")]), "encoding_denied"),
        (
            response(gzip.compress(b"a" * 1000000), headers=[("Content-Encoding", "gzip")]),
            "invalid_compression|response_too_large",
        ),
        (
            response(gzip.compress(b"{}")[:-3], headers=[("Content-Encoding", "gzip")]),
            "invalid_compression",
        ),
        (
            response(gzip.compress(b"{}") * 2, headers=[("Content-Encoding", "gzip")]),
            "invalid_compression",
        ),
    ]:
        transport, _, _, _, params = setup_transport(raw)
        with pytest.raises(DiscoveryError, match=code):
            exchange(transport, params)
    transport, _, _, _, params = setup_transport(
        response(gzip.compress(b'{"ok":true}'), headers=[("Content-Encoding", "gzip")]),
    )
    assert exchange(transport, params) == b'{"ok":true}'


def test_response_byte_limits_framed_chunked_and_close_delimited():
    raws = [
        response(b"x" * 20),
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + b"x" * 20,
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
        b"14\r\nxxxxxxxxxxxxxxxxxxxx\r\n0\r\n\r\n",
    ]
    for raw in raws:
        transport, _, _, _, params = setup_transport(
            raw, settings=APISettings(enabled=True, max_wire_bytes=10)
        )
        with pytest.raises(DiscoveryError, match="^response_too_large$"):
            exchange(transport, params)
    transport, _, _, _, params = setup_transport(response(b"x" * 20))
    with pytest.raises(DiscoveryError, match="^response_too_large$"):
        exchange(transport, params, limit=10)


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError("secret"), "response_timeout"),
        (ConnectionResetError("secret"), "connection_interrupted"),
        (http.client.BadStatusLine("secret"), "connection_interrupted"),
    ],
)
def test_failure_retry_exhaustion(error, code):
    transport, wire, timer, _, params = setup_transport(error, error, error)
    with pytest.raises(DiscoveryError, match="^" + code + "$"):
        exchange(transport, params)
    assert len(wire.calls) == 3 and timer.waits == [1, 1.5]


def test_interrupted_body_is_never_returned():
    raw = response(b'{"ok":true}').replace(b"Content-Length: 11", b"Content-Length: 100")
    transport, wire, _, _, params = setup_transport(raw, raw, raw)
    with pytest.raises(DiscoveryError, match="^connection_interrupted$"):
        exchange(transport, params)
    assert len(wire.calls) == 3


@pytest.mark.parametrize("retry_after", ["2", format_datetime(NOW + timedelta(seconds=2))])
def test_429_retry_after_then_success(retry_after):
    transport, wire, timer, _, params = setup_transport(
        response(status=429, headers=[("Retry-After", retry_after)]),
        response(),
    )
    assert exchange(transport, params) == b"{}"
    assert len(wire.calls) == 2 and timer.now == 2 and transport.retries == 1


def test_5xx_exhausted_and_retry_after_does_not_beat_deadline():
    transport, wire, _, _, params = setup_transport(*[response(status=503)] * 3)
    with pytest.raises(DiscoveryError, match="^provider_unavailable$"):
        exchange(transport, params)
    assert len(wire.calls) == 3
    transport, wire, timer, _, params = setup_transport(
        response(status=429, headers=[("Retry-After", "120")])
    )
    with pytest.raises(DiscoveryError, match="^deadline_exceeded$"):
        exchange(transport, params)
    assert len(wire.calls) == 1 and timer.now == 0


def test_total_deadline_includes_dns_and_response_and_backoff():
    for phase in ("dns", "response"):
        transport, wire, timer, _, params = setup_transport()
        if phase == "dns":

            def resolve(_, timer=timer):
                timer.now = 61
                return (ip_address("93.184.215.14"),)

            transport._resolver = resolve
        else:
            wire.on_open = lambda timer=timer: timer.sleep(61)
        with pytest.raises(DiscoveryError, match="^deadline_exceeded$"):
            exchange(transport, params)


def test_shared_budget_across_objects_and_keyed_ceiling():
    timer = SimulatedClock()
    budget = ProviderBudget(clock=timer, sleeper=timer.sleep)
    budget.register(3)
    for _ in range(7):
        budget.wait(20)
    assert timer.now == pytest.approx(2)
    with pytest.raises(DiscoveryError):
        APISettings(requests_per_second=4)
    APISettings(api_key="synthetic-key-00000000", requests_per_second=10)
    with pytest.raises(DiscoveryError):
        APISettings(api_key="synthetic-key-00000000", requests_per_second=11)
    with pytest.raises(DiscoveryError):
        APISettings(workers=2)
    # Default transport instances all share the same provider singleton.
    p, a, _, _ = demo_transport()
    a = OperationPolicyGate(a)
    first = SecureMetadataTransport(p, a)
    second = SecureMetadataTransport(p, a)
    assert first._budget is second._budget


def test_live_requires_exclusive_egress_and_conflicting_process_fails_closed(monkeypatch):
    transport, _, _, _, params = setup_transport()
    transport.is_live = True
    with pytest.raises(DiscoveryError, match="^shared_ip_uncoordinated$"):
        exchange(transport, params)
    transport.settings = replace(transport.settings, exclusive_provider_ip=True)
    monkeypatch.setattr(api_transport, "_LEASE", object())
    monkeypatch.setattr(api_transport, "_LEASE_PID", -1)
    with pytest.raises(DiscoveryError, match="^worker_conflict$"):
        exchange(transport, params)


def test_secrets_only_in_post_body_not_urls_repr_reports_or_logs(caplog):
    settings = APISettings(
        enabled=True, email="private@example.invalid", api_key="synthetic-secret-00000"
    )
    transport, wire, _, _, params = setup_transport(response(status=401), settings=settings)
    with pytest.raises(DiscoveryError) as caught:
        exchange(transport, params)
    assert b"api_key=synthetic-secret-00000" in wire.calls[0][3]
    assert b"email=private%40example.invalid" in wire.calls[0][3]
    visible = repr(settings) + str(caught.value) + caplog.text + wire.calls[0][1]
    assert "synthetic-secret" not in visible and "private@" not in visible
