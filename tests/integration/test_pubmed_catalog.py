import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from pubmed_helpers import NOW, Transport, configuration, connector, load

from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    CatalogError,
    Document,
    DocumentRelation,
    Identifier,
    Observation,
    PolicyReference,
    Rendition,
    Source,
    SourceItem,
)
from medical_data_crawler.catalog.discovery import CatalogDiscoveryWriter, local_id
from medical_data_crawler.discovery import ALLOWED_FIELDS


@pytest.fixture
def setup(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain("test-domain"))
        yield catalog, catalog.domain("test-domain")


def test_full_discovery_replay_updated_claims_and_no_artifacts(setup):
    catalog, scope = setup
    snapshot, request, permit = configuration()
    transport = Transport()
    writer = CatalogDiscoveryWriter(scope, connector(transport))
    current = request
    for _ in range(3):
        outcome = writer.run(current, permit)
        assert outcome.report.accepted == 2
        if outcome.next_cursor:
            current = replace(request, cursor=outcome.next_cursor)
    assert outcome.report.status == "complete"
    before = scope.list(Observation, limit=1000)
    # Replay with a later observation clock retains the original timestamp and exact rows.
    later = NOW.replace(hour=9)
    writer.connector = connector(transport, clock=lambda: later)
    assert writer.run(request, permit).report.accepted == 2
    assert scope.list(Observation, limit=1000) == before
    transport.summary = load("esummary-updated.json")
    assert writer.run(request, permit).report.accepted == 2
    item = scope.find_source_item("pubmed", snapshot.pmids[0])
    titles = scope.observations(item.document_id, field="title")
    assert len(titles) == 2 and len({t.value for t in titles}) == 2
    assert {t.observed_at for t in titles} == {NOW.isoformat(), later.isoformat()}
    assert all("mapping=pubmed-esummary-2.0-v1" in t.evidence for t in titles)
    assert all("path=title" in t.evidence and "permit=" in t.evidence for t in titles)
    assert len(scope.list(Document)) == len(scope.list(SourceItem)) == 6
    assert scope.list(Rendition) == ()
    assert scope.list(DocumentRelation) == ()
    assert all(d.scope == d.audience == "unknown" for d in scope.list(Document))
    assert len(scope.list(Document, category="systematic_reviews")) == 1
    assert (
        scope.get(Document, local_id(request.domain_id, "document", "990000004")).category
        == "unknown"
    )
    for namespace, value in (
        ("pmid", "990000006"),
        ("doi", "10.99999/fictional-skin-0"),
        ("pmcid", "PMC990000006"),
    ):
        assert scope.find_identifier(namespace, value).document_id == item.document_id
    statuses = [o for o in scope.list(Observation, limit=1000) if o.field == "status"]
    assert len(statuses) == 3 and all("unresolved_review_candidate" in o.value for o in statuses)
    serialized = json.dumps([asdict(o) for o in scope.list(Observation, limit=1000)])
    for forbidden in (
        "UNAUTHORIZED_",
        "DROP_UNKNOWN_",
        "publisher.example",
        "openaccess",
        request.query,
        "abstract",
    ):
        assert forbidden not in serialized
    catalog.verify()
    # Inspect all persisted tables, including policy/source records and hidden JSON values.
    database_text = "\n".join(catalog._connection.iterdump())
    for forbidden in ("UNAUTHORIZED_", "DROP_UNKNOWN_", request.query, "publisher.example"):
        assert forbidden not in database_text


@pytest.mark.parametrize(
    "fields",
    [frozenset({"pmid"}), ALLOWED_FIELDS - {"title"}, ALLOWED_FIELDS - {"doi", "pmcid", "status"}],
)
def test_permit_fields_control_all_persistence(setup, fields):
    _, scope = setup
    _, request, permit = configuration()
    outcome = CatalogDiscoveryWriter(scope, connector(Transport())).run(
        request, replace(permit, fields=fields)
    )
    assert outcome.report.accepted == 2
    assert {o.field for o in scope.list(Observation, limit=1000)} <= fields
    assert {i.namespace for i in scope.list(Identifier)} <= fields
    if "category" not in fields:
        assert all(d.category == "unknown" for d in scope.list(Document))


@pytest.mark.parametrize(
    "change",
    [
        {"allow_discovery": False},
        {"allow_retention": False},
        {"query": "unapproved secret"},
        {"valid_until": NOW},
    ],
)
def test_denied_request_creates_no_catalog_records(setup, change):
    _, scope = setup
    _, request, permit = configuration()
    transport = Transport()
    result = CatalogDiscoveryWriter(scope, connector(transport)).run(
        request, replace(permit, **change)
    )
    assert result.report.status == "failed" and result.next_cursor is None
    assert scope.list(Source) == scope.list(Document) == scope.list(PolicyReference) == ()
    assert transport.calls == []
    assert "secret" not in json.dumps(asdict(result.report))


def test_cross_domain_writer_rejected_before_io_and_fk_remains_enforced(setup):
    catalog, scope = setup
    _, request, permit = configuration()
    catalog.create_domain(AccessDomain("other", "internal"))
    other = catalog.domain("other")
    transport = Transport()
    result = CatalogDiscoveryWriter(other, connector(transport)).run(request, permit)
    assert result.report.issues[0].code == "domain_mismatch" and transport.calls == []
    assert scope.list(Document) == other.list(Document) == ()
    scope.write(Document(request.domain_id, "only-here"))
    with pytest.raises(CatalogError, match="^invalid_reference$"):
        other.write(
            Source("other", "source", "Synthetic", "fixture"),
            SourceItem("other", "item", "source", "1", "only-here"),
        )
    assert other.list(Source) == ()


def test_missing_and_invalid_items_commit_good_records_then_retry(setup):
    _, scope = setup
    _, request, permit = configuration()
    transport = Transport(summary=load("esummary-missing.json"))
    writer = CatalogDiscoveryWriter(scope, connector(transport))
    result = writer.run(request, permit)
    assert result.report.accepted == 1 and result.report.rejected == 1
    assert result.next_cursor is None
    assert len(scope.list(Document)) == 1
    before = scope.list(Observation, limit=1000)
    transport.summary = None
    assert writer.run(request, permit).next_cursor is not None
    assert len(scope.list(Document)) == 2
    assert all(o in scope.list(Observation, limit=1000) for o in before)


def test_item_transaction_failure_rolls_back_and_other_items_survive(setup, monkeypatch):
    _, scope = setup
    _, request, permit = configuration()
    original = scope._put

    def fail_after_document(record):
        original(record)
        if isinstance(record, SourceItem) and record.native_key == "990000006":
            raise CatalogError("database_error")

    monkeypatch.setattr(scope, "_put", fail_after_document)
    writer = CatalogDiscoveryWriter(scope, connector(Transport()))
    result = writer.run(request, permit)
    assert result.report.accepted == result.report.rejected == 1
    assert result.next_cursor is None
    assert scope.find_source_item("pubmed", "990000006") is None
    assert scope.get(Document, local_id(request.domain_id, "document", "990000006")) is None
    assert len(scope.list(Document)) == 1
    monkeypatch.setattr(scope, "_put", original)
    assert writer.run(request, permit).report.accepted == 2
    assert len(scope.list(Document)) == 2


def test_same_doi_or_title_hints_never_merge_documents(setup):
    _, scope = setup
    _, request, permit = configuration()
    summary = load("esummary-0.json")
    first = summary["result"]["990000006"]
    second = summary["result"]["990000005"]
    second["title"] = first["title"]
    second["articleids"].append({"idtype": "doi", "value": "10.99999/fictional-skin-0"})
    result = CatalogDiscoveryWriter(scope, connector(Transport(summary=summary))).run(
        request, permit
    )
    assert result.report.accepted == 2 and len(scope.list(Document)) == 2
    assert len([o for o in scope.list(Observation, limit=1000) if o.field == "doi"]) == 2
    assert len([i for i in scope.list(Identifier) if i.namespace == "doi"]) == 1


def test_pmid_owned_by_another_document_is_reviewed_without_merging(setup):
    _, scope = setup
    _, request, permit = configuration()
    scope.write(
        Document(request.domain_id, "reviewed-document"),
        Identifier(
            request.domain_id,
            "existing-pmid",
            "pmid",
            "990000006",
            "reviewed-document",
            "synthetic-review",
        ),
    )
    result = CatalogDiscoveryWriter(scope, connector(Transport())).run(request, permit)
    assert result.report.accepted == 1 and result.report.rejected == 1
    assert result.report.issues[0].code == "identity_conflict"
    assert scope.find_identifier("pmid", "990000006").document_id == "reviewed-document"
    assert scope.find_source_item("pubmed", "990000006") is None


def test_expiry_immediately_before_write_prevents_publication(setup, monkeypatch):
    _, scope = setup
    _, request, permit = configuration()
    now = [NOW]
    service = connector(Transport(), clock=lambda: now[0])
    original = scope.find_identifier

    def expire(namespace, value):
        result = original(namespace, value)
        now[0] = permit.valid_until
        return result

    monkeypatch.setattr(scope, "find_identifier", expire)
    result = CatalogDiscoveryWriter(scope, service).run(request, permit)
    assert result.report.accepted == 0 and result.next_cursor is None
    assert scope.list(Document) == scope.list(Source) == ()


def test_demo_twice_with_socket_guard_and_persistent_state(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/demo_pubmed_discovery.py"
    code = """
import runpy, socket, sys
def blocked(*args, **kwargs):
    raise AssertionError('Demo must be offline')
socket.socket.connect = socket.socket.connect_ex = blocked
socket.create_connection = socket.getaddrinfo = blocked
runpy.run_path(sys.argv[1], run_name='__main__')
"""
    outputs = []
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", code, str(script)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1]
    assert outputs[0]["documents"] == 6 and outputs[0]["observations"] == 52
    assert outputs[0]["renditions"] == outputs[0]["network_requests"] == 0
    assert (tmp_path / "data/pubmed-discovery-demo/report.json").is_file()
