"""Replay fictional PubMed metadata only. All generated state stays under data/."""

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    Document,
    Observation,
    Rendition,
    SourceItem,
)
from medical_data_crawler.catalog.discovery import CatalogDiscoveryWriter, local_id
from medical_data_crawler.discovery import DiscoveryPermit, DiscoveryRequest, SearchSnapshot
from medical_data_crawler.pubmed import ESEARCH, ESUMMARY, PubMedDiscoveryConnector

FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/pubmed"
NOW = datetime(2026, 11, 24, 8, tzinfo=UTC)
# Public synthetic signing material, not a credential. Real deployment supplies an operator key.
FIXTURE_CURSOR_KEY = b"public-synthetic-cursor-key-v1-0000"


def configuration(domain="pubmed-fixtures"):
    raw = json.loads((FIXTURES / "snapshot.json").read_text(encoding="utf-8"))
    snapshot = SearchSnapshot(**{**raw, "pmids": tuple(raw["pmids"])})
    request = DiscoveryRequest(domain, snapshot.profile_id, snapshot.query)
    permit = DiscoveryPermit(
        "synthetic-metadata-approval-v1",
        domain,
        snapshot.profile_id,
        snapshot.query,
        datetime(2026, 11, 1, tzinfo=UTC),
        datetime(2026, 12, 1, tzinfo=UTC),
        allow_discovery=True,
        allow_retention=True,
    )
    return snapshot, request, permit


class FixtureTransport:
    """Exact offline exchanges. No network imports and no response-derived paths."""

    def __init__(self):
        self.summary_variant = None
        self.calls = 0

    def exchange(self, endpoint, parameters, *, max_bytes):
        self.calls += 1
        if endpoint == ESEARCH:
            assert set(parameters) == {"db", "term", "retmode", "retstart", "retmax", "sort"}
            assert parameters["retmax"] == "2"
            offset = parameters["retstart"]
            assert offset in {"0", "2", "4"}
            name = f"esearch-{offset}.json"
        else:
            assert endpoint == ESUMMARY
            assert set(parameters) == {"db", "id", "retmode", "version"}
            assert parameters["version"] == "2.0"
            offset = {
                "990000006,990000005": "0",
                "990000004,990000003": "2",
                "990000002,990000001": "4",
            }[parameters["id"]]
            name = f"esummary-{offset}.json"
            if offset == "0" and self.summary_variant is not None:
                assert self.summary_variant in {"updated", "missing"}
                name = f"esummary-{self.summary_variant}.json"
        assert parameters["db"] == "pubmed" and parameters["retmode"] == "json"
        with (FIXTURES / name).open("rb") as stream:
            payload = stream.read(max_bytes + 1)
        return payload


def run_demo(output=Path("data/pubmed-discovery-demo")):
    snapshot, request, permit = configuration()
    transport = FixtureTransport()
    connector = PubMedDiscoveryConnector(
        snapshot, cursor_key=FIXTURE_CURSOR_KEY, transport=transport, clock=lambda: NOW
    )
    reports = []
    with Catalog(output) as catalog:
        catalog.create_domain(AccessDomain(request.domain_id))
        scope = catalog.domain(request.domain_id)
        writer = CatalogDiscoveryWriter(scope, connector)
        first = writer.run(request, permit)
        assert first.next_cursor
        second = writer.run(replace(request, cursor=first.next_cursor), permit)
        assert second.next_cursor
        third = writer.run(replace(request, cursor=second.next_cursor), permit)
        assert third.report.status == "complete"
        reports.extend([first.report, second.report, third.report])
        before = len(scope.list(Observation, limit=1000))
        replay = writer.run(request, permit)
        assert len(scope.list(Observation, limit=1000)) == before
        reports.append(replay.report)
        transport.summary_variant = "updated"
        reports.append(writer.run(request, permit).report)
        transport.summary_variant = "missing"
        missing = writer.run(request, permit)
        assert missing.next_cursor is None and missing.report.status == "incomplete"
        reports.append(missing.report)
        document_id = local_id(request.domain_id, "document", snapshot.pmids[0])
        assert len(scope.observations(document_id, field="title")) == 2
        assert len(scope.list(Document)) == len(scope.list(SourceItem)) == 6
        assert scope.list(Rendition) == ()
        assert all(d.scope == d.audience == "unknown" for d in scope.list(Document))
        assert all("UNAUTHORIZED_" not in str(o.value) for o in scope.list(Observation, limit=1000))
        catalog.verify()
        result = {
            "integrity": "pass",
            "network_requests": 0,
            "documents": 6,
            "observations": len(scope.list(Observation, limit=1000)),
            "renditions": 0,
            "title_observations": 2,
            "reports": [asdict(report) for report in reports],
        }
    (output / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
