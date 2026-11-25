"""Shared synthetic replay builders; no external I/O."""

import json
from datetime import UTC, datetime
from pathlib import Path

from medical_data_crawler.discovery import DiscoveryPermit, DiscoveryRequest, SearchSnapshot
from medical_data_crawler.pubmed import ESEARCH, ESUMMARY, PubMedDiscoveryConnector

FIXTURES = Path(__file__).parent / "fixtures/pubmed"
NOW = datetime(2026, 11, 24, 8, tzinfo=UTC)
KEY = b"public-synthetic-test-cursor-key-0000"


def load(name):
    return json.loads((FIXTURES / name).read_bytes())


def configuration():
    raw = load("snapshot.json")
    snapshot = SearchSnapshot(**{**raw, "pmids": tuple(raw["pmids"])})
    request = DiscoveryRequest("test-domain", snapshot.profile_id, snapshot.query)
    permit = DiscoveryPermit(
        "test-permit",
        request.domain_id,
        snapshot.profile_id,
        snapshot.query,
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 12, 1, tzinfo=UTC),
        allow_discovery=True,
        allow_retention=True,
    )
    return snapshot, request, permit


class Transport:
    def __init__(self, search=None, summary=None):
        self.search = search
        self.summary = summary
        self.calls = []
        self.failure = None
        self.after_exchange = lambda: None

    def exchange(self, endpoint, parameters, *, max_bytes):
        self.calls.append((endpoint, parameters, max_bytes))
        if self.failure:
            raise self.failure
        self.after_exchange()
        if endpoint == ESEARCH:
            value = (
                self.search
                if self.search is not None
                else load(f"esearch-{parameters['retstart']}.json")
            )
        else:
            assert endpoint == ESUMMARY
            if self.summary is not None:
                value = self.summary
            else:
                offset = {
                    "990000006,990000005": 0,
                    "990000004,990000003": 2,
                    "990000002,990000001": 4,
                }[parameters["id"]]
                value = load(f"esummary-{offset}.json")
        return value if type(value) is bytes else json.dumps(value).encode()


def connector(transport=None, snapshot=None, clock=lambda: NOW):
    return PubMedDiscoveryConnector(
        snapshot or configuration()[0], cursor_key=KEY, transport=transport, clock=clock
    )
