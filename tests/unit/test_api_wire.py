"""Exercise production socket/TLS wiring with simulated socket bytes only."""

import socket
import ssl
import subprocess
import sys
from io import BytesIO
from ipaddress import ip_address

import pytest

from medical_data_crawler._https_transport import DirectHTTPSTransport
from medical_data_crawler.api_transport import HOST


@pytest.mark.parametrize("peer", ["93.184.215.14", "127.0.0.1"])
def test_post_pins_peer_and_uses_verified_hostname_with_secrets_only_in_body(monkeypatch, peer):
    sent, connected = [], []
    wire = BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")

    class FakeSocket:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, seconds):
            assert 0 < seconds <= 5

        def connect(self, endpoint):
            connected.append(endpoint)

        def getpeername(self):
            return peer, 443

        def sendall(self, payload):
            sent.append(payload)

        def recv_into(self, buffer):
            return wire.readinto(buffer)

    def wrap(context, sock, *, server_hostname):
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        assert context.minimum_version == ssl.TLSVersion.TLSv1_2
        assert context.keylog_filename is None
        assert context.cert_store_stats()["x509_ca"] > 0
        assert server_hostname == HOST
        return sock

    monkeypatch.setattr(socket, "socket", FakeSocket)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    monkeypatch.setenv("SSLKEYLOGFILE", "MUST_NOT_CREATE")
    monkeypatch.setenv("HTTPS_PROXY", "http://MUST_NOT_CONTACT.invalid")
    transport = DirectHTTPSTransport(connect_timeout=5, read_timeout=5, request_timeout=5)
    from time import monotonic

    def run():
        with transport.post(
            HOST,
            "/entrez/eutils/esearch.fcgi",
            ip_address("93.184.215.14"),
            "SyntheticBot",
            body=b"api_key=synthetic-only",
            deadline=monotonic() + 5,
            before_send=lambda: None,
        ) as response:
            assert response.read(2) == b"{}"

    if peer == "127.0.0.1":
        with pytest.raises(ConnectionError):
            run()
        assert sent == []
    else:
        run()
        header, body = sent[0].split(b"\r\n\r\n")
        assert b"POST /entrez/eutils/esearch.fcgi HTTP/1.1" in header
        assert b"api_key" not in header and body == b"api_key=synthetic-only"
    assert connected == [("93.184.215.14", 443)]


def test_os_worker_lease_blocks_second_process(tmp_path):
    # Isolate the lock pathname but exercise real Windows/POSIX OS file locking.
    holder_code = """
import sys
from medical_data_crawler import api_transport as api
api.tempfile.gettempdir = lambda: sys.argv[1]
api._single_process_lease()
print('held', flush=True)
sys.stdin.readline()
"""
    probe_code = """
import sys
from medical_data_crawler import api_transport as api
from medical_data_crawler.discovery import DiscoveryError
api.tempfile.gettempdir = lambda: sys.argv[1]
try:
    api._single_process_lease()
except DiscoveryError as e:
    assert e.code == 'worker_conflict'
    print('blocked')
else:
    raise AssertionError('A second worker acquired the provider lease')
"""
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_code, str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        probe = subprocess.run(
            [sys.executable, "-c", probe_code, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        assert probe.stdout.strip() == "blocked"
    finally:
        holder.communicate(input="\n", timeout=20)
