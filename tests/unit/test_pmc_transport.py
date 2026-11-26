"""XML transport fault injection; shared wire TLS tests remain regression coverage."""

import ssl
from contextlib import contextmanager
from email.message import Message
from ipaddress import ip_address

import pytest

from medical_data_crawler.discovery import DiscoveryError
from medical_data_crawler.pmc_transport import PMCTransport


class Response:
    status = 200

    def __init__(self, body=b"<xml/>", headers=None):
        self.body = body
        self.headers = Message()
        for key, value in (headers or {"Content-Type": "application/xml"}).items():
            self.headers[key] = value

    def read1(self, size):
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk


class Wire:
    def __init__(self, response):
        self.response = response
        self.calls = []

    @contextmanager
    def post(self, host, target, address, agent, **kwargs):
        self.calls.append((host, target, address, kwargs))
        kwargs["before_send"]()
        if isinstance(self.response, Exception):
            raise self.response
        yield self.response


def transport(monkeypatch, response, address="8.8.8.8"):
    monkeypatch.setattr("medical_data_crawler.pmc_transport._single_process_lease", lambda: None)
    monkeypatch.setattr("medical_data_crawler.pmc_transport._PROVIDER_BUDGET.wait", lambda _: None)
    wire = Wire(response)
    return PMCTransport(
        enabled=True,
        exclusive_provider_ip=True,
        wire=wire,
        resolver=lambda _: (ip_address(address),),
    ), wire


def test_xml_exchange_pinned_endpoint_and_profile(monkeypatch):
    client, wire = transport(monkeypatch, Response())
    assert client.fetch("PMC123", lambda: None) == b"<xml/>"
    host, target, address, kwargs = wire.calls[0]
    assert host == "pmc.ncbi.nlm.nih.gov" and target == "/api/oai/v1/mh/"
    assert address == ip_address("8.8.8.8")
    assert kwargs["accept"] == "application/xml"
    assert b"metadataPrefix=pmc" in kwargs["body"]
    assert b"identifier=oai%3Apubmedcentral.nih.gov%3A123" in kwargs["body"]


@pytest.mark.parametrize(
    "status,code",
    [
        (301, "redirect_denied"),
        (302, "redirect_denied"),
        (429, "rate_limited"),
        (503, "rate_limited"),
        (404, "http_status_denied"),
    ],
)
def test_status_no_retry(monkeypatch, status, code):
    response = Response()
    response.status = status
    client, wire = transport(monkeypatch, response)
    with pytest.raises(DiscoveryError, match=code):
        client.fetch("PMC1", lambda: None)
    assert len(wire.calls) == 1


@pytest.mark.parametrize(
    "headers,code",
    [
        ({"Content-Type": "text/html"}, "content_type_denied"),
        ({"Content-Type": "application/xml", "Content-Encoding": "gzip"}, "encoding_denied"),
        ({"Content-Type": "application/xml", "Content-Length": "999999999"}, "xml_size_denied"),
        ({"Content-Type": "application/xml", "Content-Length": "100"}, "incomplete_response"),
        (
            {
                "Content-Type": "application/xml",
                "Content-Length": "6",
                "Transfer-Encoding": "chunked",
            },
            "invalid_headers",
        ),
    ],
)
def test_headers(monkeypatch, headers, code):
    client, _ = transport(monkeypatch, Response(headers=headers))
    with pytest.raises(DiscoveryError, match=code):
        client.fetch("PMC1", lambda: None)


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "::1", "10.1.1.1"])
def test_ssrf_never_reaches_wire(monkeypatch, address):
    client, wire = transport(monkeypatch, Response(), address)
    with pytest.raises(DiscoveryError, match="unsafe_address"):
        client.fetch("PMC1", lambda: None)
    assert not wire.calls


@pytest.mark.parametrize(
    "error,code", [(ssl.SSLError(), "tls_failure"), (TimeoutError(), "response_timeout")]
)
def test_wire_failure(monkeypatch, error, code):
    client, _ = transport(monkeypatch, error)
    with pytest.raises(DiscoveryError, match=code):
        client.fetch("PMC1", lambda: None)
