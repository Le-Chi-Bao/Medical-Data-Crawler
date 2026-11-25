"""Direct, single-use HTTP/1.1 connections to an already validated numeric IP."""

import http.client
import io
import socket
import ssl
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from ipaddress import IPv4Address, IPv6Address, ip_address
from time import monotonic

import certifi

IPAddress = IPv4Address | IPv6Address


def resolve_host(host: str) -> tuple[IPAddress, ...]:
    # A fully qualified DNS query avoids resolver search-suffix expansion.
    answers = socket.getaddrinfo(host + ".", 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
    try:
        return tuple(ip_address(sockaddr[0]) for _, _, _, _, sockaddr in answers)
    except ValueError:
        raise ConnectionError from None


def _remaining(deadline: float, limit: float) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError
    return min(remaining, limit)


class _DeadlineReader(io.RawIOBase):
    def __init__(self, sock: ssl.SSLSocket, deadline: float, read_timeout: float):
        self.sock = sock
        self.deadline = deadline
        self.read_timeout = read_timeout

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        self.sock.settimeout(_remaining(self.deadline, self.read_timeout))
        return self.sock.recv_into(buffer)

    def makefile(self, mode: str) -> io.BufferedReader:
        # HTTPResponse consumes this buffered binary file. Each underlying read
        # gets a fresh idle timeout capped by the absolute request deadline.
        return io.BufferedReader(self)


class DirectHTTPSTransport:
    def __init__(self, *, connect_timeout: float, read_timeout: float, request_timeout: float):
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.request_timeout = request_timeout

    @contextmanager
    def get(
        self,
        host: str,
        target: str,
        address: IPAddress,
        user_agent: str,
        *,
        before_send: Callable[[], None],
    ) -> Iterator[http.client.HTTPResponse]:
        with self._request(
            host,
            target,
            address,
            user_agent,
            before_send=before_send,
        ) as response:
            yield response

    @contextmanager
    def post(
        self,
        host: str,
        target: str,
        address: IPAddress,
        user_agent: str,
        *,
        body: bytes,
        deadline: float,
        before_send: Callable[[], None],
    ) -> Iterator[http.client.HTTPResponse]:
        """Form POST keeps contact settings and optional credentials out of URLs."""
        with self._request(
            host,
            target,
            address,
            user_agent,
            before_send=before_send,
            body=body,
            deadline=deadline,
        ) as response:
            yield response

    @contextmanager
    def _request(
        self,
        host,
        target,
        address,
        user_agent,
        *,
        before_send,
        body=None,
        deadline=None,
    ):
        # Use the packaged CA bundle and a fresh verified context. Environment
        # proxy, CA override, client credentials and TLS key logging are unused.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        try:
            context.load_verify_locations(cafile=certifi.where())
        except OSError:
            raise ssl.SSLError from None
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        family = socket.AF_INET if address.version == 4 else socket.AF_INET6
        deadline = min(
            deadline if deadline is not None else float("inf"),
            monotonic() + self.request_timeout,
        )
        connect_deadline = min(deadline, monotonic() + self.connect_timeout)
        with socket.socket(family, socket.SOCK_STREAM) as raw:
            raw.settimeout(_remaining(connect_deadline, self.connect_timeout))
            raw.connect((str(address), 443))
            if ip_address(raw.getpeername()[0]) != address:
                raise ConnectionError
            raw.settimeout(_remaining(connect_deadline, self.connect_timeout))
            with context.wrap_socket(raw, server_hostname=host) as tls:
                before_send()
                tls.settimeout(_remaining(deadline, self.read_timeout))
                # The adapter validates the hostname, origin-form target and UA
                # before calling this transport. No credentials cross requests.
                method = "GET" if body is None else "POST"
                extra = (
                    "Accept: text/html, application/pdf\r\nAccept-Encoding: identity\r\n"
                    if body is None
                    else "Accept: application/json\r\n"
                    "Accept-Encoding: gzip, identity\r\n"
                    "Content-Type: application/x-www-form-urlencoded\r\n"
                    f"Content-Length: {len(body)}\r\n"
                )
                tls.sendall(
                    (
                        f"{method} {target} HTTP/1.1\r\n"
                        f"Host: {host}\r\n"
                        f"User-Agent: {user_agent}\r\n"
                        f"{extra}"
                        "Connection: close\r\n\r\n"
                    ).encode("ascii")
                    + (body or b"")
                )
                reader = _DeadlineReader(tls, deadline, self.read_timeout)
                with http.client.HTTPResponse(reader) as response:
                    response.begin()
                    yield response
