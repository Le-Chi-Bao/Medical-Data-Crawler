"""Synthetic HTTP responses for transport tests; no sockets or DNS."""

import http.client
import json
from collections import deque
from contextlib import contextmanager
from ipaddress import ip_address

from medical_data_crawler.api_transport import APISettings, ProviderBudget, SecureMetadataTransport
from medical_data_crawler.operation_policy import OperationPolicyGate
from medical_data_crawler.secure_api_demo import NOW, _SocketBytes, demo_transport


def response(body=b"{}", *, status=200, headers=()):
    if not isinstance(body, bytes):
        body = json.dumps(body).encode()
    standard = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    return (
        f"HTTP/1.1 {status} Synthetic\r\n".encode()
        + "".join(f"{k}: {v}\r\n" for k, v in [*standard, *headers]).encode()
        + b"\r\n"
        + body
    )


class Wire:
    def __init__(self, *responses):
        self.responses = deque(responses or [response()])
        self.calls = []
        self.on_open = lambda: None

    @contextmanager
    def post(self, host, target, address, user_agent, *, body, deadline, before_send):
        before_send()
        self.calls.append((host, target, address, body, deadline))
        self.on_open()
        raw = self.responses.popleft()
        if isinstance(raw, BaseException):
            raise raw
        with http.client.HTTPResponse(_SocketBytes(raw)) as incoming:
            incoming.begin()
            yield incoming


def setup_transport(*responses, settings=None, resolver=None, wire=None, budget=None):
    permit, authority, timer, _ = demo_transport()
    wire = wire if wire is not None else Wire(*responses)
    budget = budget if budget is not None else ProviderBudget(clock=timer, sleeper=timer.sleep)
    transport = SecureMetadataTransport(
        permit,
        OperationPolicyGate(authority),
        settings=settings or APISettings(enabled=True),
        wire=wire,
        resolver=resolver or (lambda _: (ip_address("93.184.215.14"),)),
        budget=budget,
        clock=timer,
        wall_clock=lambda: NOW,
        sleeper=timer.sleep,
        jitter=lambda: 0.5,
    )
    parameters = {
        "db": "pubmed",
        "term": permit.query,
        "retmode": "json",
        "retstart": "0",
        "retmax": "2",
        "sort": "pub_date",
    }
    return transport, wire, timer, authority, parameters
