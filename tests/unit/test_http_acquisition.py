import json
import socket
import ssl
from collections import deque
from contextlib import contextmanager
from dataclasses import replace
from hashlib import sha256
from http.client import HTTPResponse
from ipaddress import ip_address

import pytest

from medical_data_crawler import http_acquisition
from medical_data_crawler.acquisition import DocumentRequest
from medical_data_crawler.http_acquisition import HTTPAcquisitionSettings, HTTPDocumentAdapter
from medical_data_crawler.provenance import ProvenanceError, ProvenanceStore
from medical_data_crawler.storage import ArtifactStore, StorageError
from scripts.demo_http_acquisition import USER_AGENT, MemorySocket, synthetic_source, wire_response

HOST = "publisher.example"
IP = ip_address("93.184.215.14")
HTML = b"<h1>Synthetic</h1>\r\n<p>Fixture bytes.</p>"


class ScriptedTransport:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.calls = []

    @contextmanager
    def get(self, host, target, address, user_agent, *, before_send):
        before_send()
        self.calls.append((host, target, address, user_agent))
        payload = self.responses.popleft()
        if isinstance(payload, Exception):
            raise payload
        with HTTPResponse(MemorySocket(payload)) as response:
            response.begin()
            yield response


def encoded(body=HTML, content_type="text/html", length=None, headers=()):
    return wire_response(
        body,
        headers=(
            ("Content-Type", content_type),
            ("Content-Length", str(len(body) if length is None else length)),
            *headers,
        ),
    )


@pytest.fixture
def harness(tmp_path, monkeypatch):
    artifacts = ArtifactStore(tmp_path / "originals")
    provenance = ProvenanceStore(tmp_path / "events", artifacts)
    source = synthetic_source(HOST, "/sample.html", "html")
    request = DocumentRequest(None, source["source_id"], "sample", source["candidate_url"])
    delays = []
    monkeypatch.setattr(http_acquisition, "sleep", delays.append)

    def create(*responses, sources=None, resolver=None, **options):
        transport = ScriptedTransport(responses)
        settings = {"enabled": True, "user_agent": USER_AGENT, **options}
        adapter = HTTPDocumentAdapter(
            artifacts,
            provenance,
            {"schema_version": "0.1", "sources": [source] if sources is None else sources},
            resolver=(lambda host: (IP,)) if resolver is None else resolver,
            transport=transport,
            settings=HTTPAcquisitionSettings(**settings),
        )
        return adapter, transport

    return create, source, request, delays


def event_for(adapter, result):
    return json.loads(
        (adapter.provenance.root / f"{result.event_id}.json").read_text(encoding="utf-8")
    )


def test_original_dedup_and_provenance(harness):
    create, _, request, _ = harness
    adapter, transport = create(encoded(), encoded(headers=(("Content-Encoding", "identity"),)))
    first = adapter.acquire(request)
    second = adapter.acquire(request)
    assert first.accepted and second.accepted
    assert first.artifact == second.artifact
    assert first.document_id == second.document_id and first.event_id != second.event_id
    checksum = sha256(HTML).hexdigest()
    assert list(adapter.artifacts.root.iterdir()) == [adapter.artifacts.root / checksum]
    assert (adapter.artifacts.root / checksum).read_bytes() == HTML
    assert transport.calls == [(HOST, "/sample.html", IP, USER_AGENT)] * 2
    event = event_for(adapter, second)
    assert event["sha256"] == checksum and event["byte_size"] == len(HTML)
    assert event["http"]["user_agent"] == USER_AGENT
    assert event["http"]["outcome"] == "accepted"
    assert event["http"]["attempts"] == [
        {
            "source_id": request.source_id,
            "locator": request.locator,
            "attempted_at": event["http"]["attempts"][0]["attempted_at"],
            "status": 200,
            "outcome": "accepted",
        }
    ]


def test_pdf_and_queryless_path_without_suffix(harness, pdf_bytes):
    create, _, _, _ = harness
    source = synthetic_source(HOST, "/download", "pdf")
    payload = pdf_bytes([[(72, 720, "Synthetic PDF")]])
    adapter, _ = create(encoded(payload, "application/pdf"), sources=[source])
    request = DocumentRequest(None, source["source_id"], "sample", source["candidate_url"])
    result = adapter.acquire(request)
    assert result.accepted and result.media_type == "application/pdf"
    assert (adapter.artifacts.root / result.artifact.sha256).read_bytes() == payload


def test_default_and_invalid_configuration(harness):
    create, source, request, _ = harness
    adapter, _ = create()
    default_adapter = HTTPDocumentAdapter(
        adapter.artifacts, adapter.provenance, {"schema_version": "0.1", "sources": [source]}
    )
    result = default_adapter.acquire(request)
    assert result.errors == ("http_disabled",)
    assert event_for(default_adapter, result)["http"]["attempts"] == []


@pytest.mark.parametrize(
    "options",
    [
        {"enabled": "true"},
        {"user_agent": "Bot\r\nCookie: synthetic"},
        {"max_bytes": 0},
        {"min_host_interval": 0},
        {"request_timeout": float("nan")},
        {"max_retries": 1000},
        {"max_redirects": 1000},
    ],
)
def test_configuration_fails_closed(options):
    with pytest.raises(ValueError, match="^invalid_http_"):
        HTTPAcquisitionSettings(**options)


@pytest.mark.parametrize("case", ["unapproved", "expired", "missing_rights", "wrong_agent", "id"])
def test_denied_before_dns(harness, case):
    create, source, request, _ = harness
    options = {}
    if case == "unapproved":
        source.update(status="needs_review", automated_acquisition="unknown")
    elif case == "expired":
        source["review"].update(
            reviewed_at="2000-01-01T00:00:00Z", review_again_at="2000-01-02T00:00:00Z"
        )
    elif case == "missing_rights":
        del source["rights"]["original_bytes"]["internal_storage"]
    elif case == "wrong_agent":
        options["user_agent"] = USER_AGENT.lower()
    else:
        request = replace(request, source_id="unknown")

    def no_dns(host):
        pytest.fail("DNS ran without authorization")

    adapter, transport = create(resolver=no_dns, **options)
    result = adapter.acquire(request)
    assert result.errors == ("http_authorization_denied",)
    assert not transport.calls
    if case in {"unapproved", "expired", "wrong_agent"}:
        assert event_for(adapter, result)["http"]["attempts"] == []


@pytest.mark.parametrize(
    "locator",
    [
        "http://publisher.example/sample.html",
        "https://localhost/sample.html",
        "https://loopback.localhost/sample.html",
        "https://127.0.0.1/sample.html",
        "https://10.0.0.1/sample.html",
        "https://2130706433/sample.html",
        "https://0x7f.0.0.0x1/sample.html",
        "https://[::1]/sample.html",
        "https://publisher.example:443/sample.html",
        "https://user:password@publisher.example/sample.html",
        "https://publisher.example/sample.html?key=secret",
        "https://publisher.example/%73ample.html",
        "https://publisher.example/a/../sample.html",
        "https://publisher.example/sample.html#fragment",
    ],
)
def test_invalid_urls_do_not_touch_network_or_provenance(harness, locator):
    create, _, request, _ = harness
    adapter, transport = create()
    result = adapter.acquire(replace(request, locator=locator))
    assert result.errors == ("http_invalid_url",)
    assert not transport.calls and not list(adapter.provenance.root.iterdir())


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "100.64.0.1",
        "169.254.169.254",
        "224.0.0.1",
        "192.0.0.9",
        "::ffff:93.184.215.14",
        "64:ff9b::a00:1",
        "2002:0a00:1::1",
        "2001:db8::1",
    ],
)
def test_one_unsafe_dns_answer_rejects_entire_response(harness, address):
    create, _, request, _ = harness
    adapter, transport = create(resolver=lambda host: (IP, ip_address(address)))
    result = adapter.acquire(request)
    assert result.errors == ("http_unsafe_address",)
    assert not transport.calls
    assert event_for(adapter, result)["http"]["attempts"][0]["status"] is None


def test_dns_is_rechecked_after_transient_failure(harness):
    create, _, request, _ = harness
    answers = iter([(IP,), (ip_address("127.0.0.1"),)])
    adapter, transport = create(
        TimeoutError("private address"), resolver=lambda host: next(answers)
    )
    result = adapter.acquire(request)
    assert result.errors == ("http_unsafe_address",)
    assert len(transport.calls) == 1
    assert [a["outcome"] for a in event_for(adapter, result)["http"]["attempts"]] == [
        "http_timeout",
        "http_unsafe_address",
    ]


def test_expiring_review_prevents_get_after_connect(harness, monkeypatch):
    create, _, request, _ = harness
    adapter, transport = create()
    allowed = iter((True, True, False))
    monkeypatch.setattr(adapter, "_allowed", lambda source: next(allowed))
    result = adapter.acquire(request)
    assert result.errors == ("http_authorization_denied",)
    assert not transport.calls
    assert event_for(adapter, result)["http"]["attempts"][0]["status"] is None


@pytest.mark.parametrize(
    "location",
    [
        "https://unapproved.example/other.html",
        "http://publisher.example/other.html",
        "https://127.0.0.1/other.html",
        "//publisher.example/other.html",
        "/./sample.html",
        "/sample.html",
    ],
)
def test_redirect_rejection_and_loop(harness, location):
    create, _, request, _ = harness
    adapter, transport = create(wire_response(status=302, headers=(("Location", location),)))
    result = adapter.acquire(request)
    assert result.errors == ("http_redirect_rejected",)
    assert len(transport.calls) == 1
    assert event_for(adapter, result)["http"]["attempts"][0]["status"] == 302


def test_reviewed_redirects_and_host_throttle(harness):
    create, source, request, delays = harness
    second = synthetic_source(HOST, "/other.html", "html")
    third = synthetic_source("destination.example", "/sample.html", "html")
    adapter, transport = create(
        wire_response(status=301, headers=(("Location", "/other.html"),)),
        wire_response(status=307, headers=(("Location", third["candidate_url"]),)),
        encoded(),
        sources=[source, second, third],
    )
    result = adapter.acquire(request)
    assert result.accepted
    assert len(delays) == 1 and 0 < delays[0] <= adapter.settings.min_host_interval
    assert [host for host, *_ in transport.calls] == [HOST, HOST, third["domain"]]
    event = event_for(adapter, result)
    assert event["locator"] == request.locator
    assert [a["source_id"] for a in event["http"]["attempts"]] == [
        item["source_id"] for item in (source, second, third)
    ]


def test_redirect_limit(harness):
    create, source, request, _ = harness
    second = synthetic_source(HOST, "/other.html", "html")
    adapter, transport = create(
        wire_response(status=302, headers=(("Location", second["candidate_url"]),)),
        sources=[source, second],
        max_redirects=0,
    )
    assert adapter.acquire(request).errors == ("http_redirect_rejected",)
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("status", "error", "attempts"),
    [(404, "http_4xx", 1), (429, "http_4xx", 3), (500, "http_5xx", 3), (403, "http_4xx", 1)],
)
def test_http_status_retry_budget(harness, status, error, attempts):
    create, _, request, _ = harness
    adapter, transport = create(*(wire_response(status=status) for _ in range(attempts)))
    result = adapter.acquire(request)
    assert result.errors == (error,)
    assert len(transport.calls) == attempts
    assert [a["status"] for a in event_for(adapter, result)["http"]["attempts"]] == [
        status
    ] * attempts
    assert not list(adapter.artifacts.root.iterdir())


@pytest.mark.parametrize(("retry_after", "retries"), [("3", True), ("300", False), ("bad", False)])
def test_retry_after(harness, retry_after, retries):
    create, _, request, delays = harness
    adapter, transport = create(
        wire_response(status=429, headers=(("Retry-After", retry_after),)), encoded()
    )
    result = adapter.acquire(request)
    assert result.accepted == retries
    assert len(transport.calls) == (2 if retries else 1)
    assert (3 in delays) == retries


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (TimeoutError("hidden detail"), "http_timeout"),
        (ssl.SSLCertVerificationError("hidden detail"), "http_tls_failure"),
        (OSError("hidden detail"), "http_connection_failure"),
        (encoded(length=1025), "http_response_too_large"),
        (encoded(length=len(HTML) + 1), "http_incomplete_response"),
        (encoded(content_type="text/plain"), "http_unsupported_media_type"),
        (encoded(content_type="application/pdf"), "http_unsupported_media_type"),
        (encoded(headers=(("Content-Encoding", "gzip"),)), "http_unexpected_content_encoding"),
        (encoded(headers=(("Transfer-Encoding", "chunked"),)), "http_unsupported_framing"),
        (encoded(headers=(("Content-Length", str(len(HTML))),)), "http_unsupported_framing"),
        (encoded(headers=(("Content-Range", "bytes 0-9/10"),)), "http_unsupported_framing"),
        (wire_response(HTML, headers=(("Content-Type", "text/html"),)), "http_unsupported_framing"),
        (encoded(b""), "http_incomplete_response"),
    ],
)
def test_failure_has_no_artifact_and_uses_safe_error(harness, caplog, response, error):
    create, _, request, _ = harness
    adapter, _ = create(response, max_retries=0, max_bytes=1024)
    result = adapter.acquire(request)
    assert result.errors == (error,) and not result.accepted and result.artifact is None
    assert not list(adapter.artifacts.root.iterdir())
    event = event_for(adapter, result)
    assert event["status"] == "failed" and event["artifact_reference"] is None
    assert event["http"]["outcome"] == error
    assert "hidden detail" not in json.dumps(event)
    assert caplog.records == []


def test_dns_connection_failure_does_not_expose_exception(harness):
    create, _, request, _ = harness

    def broken_dns(host):
        raise socket.gaierror("sensitive DNS exception detail")

    adapter, transport = create(resolver=broken_dns, max_retries=0)
    result = adapter.acquire(request)
    assert result.errors == ("http_connection_failure",)
    assert not transport.calls
    assert "sensitive DNS" not in json.dumps(event_for(adapter, result))


def test_retry_incomplete_stream_cleans_pending_file(harness):
    create, _, request, _ = harness
    large = b"<p>" + b"x" * (4 * 65536) + b"</p>"
    adapter, transport = create(encoded(large[:-1], length=len(large)), encoded(large))
    result = adapter.acquire(request)
    assert result.accepted
    assert len(transport.calls) == 2
    assert list(adapter.artifacts.root.iterdir()) == [
        adapter.artifacts.root / sha256(large).hexdigest()
    ]


def test_transport_failure_after_body_still_prevents_publication(harness, monkeypatch):
    create, _, request, _ = harness
    adapter, transport = create(max_retries=0)

    @contextmanager
    def failed_close(*args, **kwargs):
        with HTTPResponse(MemorySocket(encoded())) as response:
            response.begin()
            yield response
        raise OSError("internal transport details")

    monkeypatch.setattr(transport, "get", failed_close)
    result = adapter.acquire(request)
    assert result.errors == ("http_connection_failure",)
    assert not list(adapter.artifacts.root.iterdir())


@pytest.mark.parametrize(
    ("store_name", "method", "exception", "code"),
    [
        ("artifacts", "put", StorageError, "http_storage_failure"),
        ("provenance", "record", ProvenanceError, "http_provenance_failure"),
    ],
)
def test_store_failures_are_isolated(harness, monkeypatch, store_name, method, exception, code):
    create, _, request, _ = harness
    adapter, transport = create(encoded())

    def broken_store(*args, **kwargs):
        raise exception("sensitive local detail")

    monkeypatch.setattr(getattr(adapter, store_name), method, broken_store)
    result = adapter.acquire(request)
    assert result.errors == (code,)
    assert not result.accepted and len(transport.calls) == 1


def test_sensitive_locations_reasons_and_bodies_are_not_logged(harness, caplog):
    create, _, request, _ = harness
    secret = "synthetic-sensitive-value"
    payload = wire_response(
        secret.encode(),
        status=302,
        headers=(("Location", f"https://publisher.example/sample.html?key={secret}"),),
    )
    adapter, _ = create(payload)
    result = adapter.acquire(request)
    assert result.errors == ("http_redirect_rejected",)
    assert secret not in json.dumps(event_for(adapter, result))
    assert secret not in caplog.text
