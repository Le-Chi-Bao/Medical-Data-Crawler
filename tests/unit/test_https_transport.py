import socket
import ssl
from collections import deque
from io import BytesIO
from ipaddress import ip_address

import pytest

from medical_data_crawler import _https_transport
from medical_data_crawler._https_transport import DirectHTTPSTransport, resolve_host


def test_dns_query_is_absolute(monkeypatch):
    def resolve(host, port, family, sock_type):
        assert (host, port, family, sock_type) == (
            "publisher.example.",
            443,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
        return [
            (socket.AF_INET, sock_type, 0, "", ("93.184.215.14", port)),
            (socket.AF_INET6, sock_type, 0, "", ("2606:4700::1111", port, 0, 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    assert resolve_host("publisher.example") == (
        ip_address("93.184.215.14"),
        ip_address("2606:4700::1111"),
    )


@pytest.mark.parametrize("pin", ["93.184.215.14", "2606:4700::1111"])
def test_direct_transport_pins_address_and_verifies_original_hostname(monkeypatch, pin):
    address = ip_address(pin)
    family = socket.AF_INET if address.version == 4 else socket.AF_INET6
    sent = []
    authorized = []
    connected = []
    timeouts = []
    wire = BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\nabc")

    class FakeSocket:
        def __init__(self, requested_family, requested_type):
            assert (requested_family, requested_type) == (family, socket.SOCK_STREAM)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def connect(self, endpoint):
            connected.append(endpoint)

        def getpeername(self):
            return pin, 443

        def settimeout(self, seconds):
            timeouts.append(seconds)

        def sendall(self, payload):
            assert authorized == [True]
            sent.append(payload)

        def recv_into(self, buffer):
            return wire.readinto(buffer)

    def wrap(context, sock, *, server_hostname):
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname
        assert context.cert_store_stats()["x509_ca"] > 0
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2
        assert context.keylog_filename is None
        assert server_hostname == "publisher.example"
        return sock

    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("SSL_CERT_FILE", "nonexistent-ca.pem")
    monkeypatch.setenv("SSLKEYLOGFILE", "unused-keys.txt")
    monkeypatch.setattr(socket, "socket", FakeSocket)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    transport = DirectHTTPSTransport(connect_timeout=5, read_timeout=2, request_timeout=8)
    with transport.get(
        "publisher.example",
        "/fixture",
        address,
        "FixtureBot",
        before_send=lambda: authorized.append(True),
    ) as response:
        assert response.read(3) == b"abc"

    assert connected == [(pin, 443)]
    assert sent == [
        b"GET /fixture HTTP/1.1\r\n"
        b"Host: publisher.example\r\n"
        b"User-Agent: FixtureBot\r\n"
        b"Accept: text/html, application/pdf\r\n"
        b"Accept-Encoding: identity\r\n"
        b"Connection: close\r\n\r\n"
    ]
    assert all(0 < seconds <= 5 for seconds in timeouts[:2])
    assert all(0 < seconds <= 2 for seconds in timeouts[2:])


def test_absolute_deadline_stops_reads_with_slow_progress(monkeypatch):
    clock = deque([2.0, 4.0, 5.5])
    monkeypatch.setattr(_https_transport, "monotonic", clock.popleft)
    timeouts = []

    class SlowSocket:
        def settimeout(self, seconds):
            timeouts.append(seconds)

        def recv_into(self, buffer):
            buffer[0] = ord("x")
            return 1

    reader = _https_transport._DeadlineReader(SlowSocket(), deadline=5.0, read_timeout=4)
    with reader.makefile("rb") as stream, pytest.raises(TimeoutError):
        stream.read(3)
    assert timeouts == [3.0, 1.0]
