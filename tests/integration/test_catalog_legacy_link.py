import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    CatalogError,
    Document,
    LegacyReference,
    Rendition,
    Revision,
    Source,
    SourceItem,
)
from medical_data_crawler.contract import validate_record
from medical_data_crawler.export import export_batch, verify_batch
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import InternalIntakeTrace, ProvenanceStore, document_id
from medical_data_crawler.storage import ArtifactStore
from scripts.demo_catalog import run_demo

FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic.html"
LOCATOR = "https://example.org/synthetic-catalog-fixture"
DOMAIN = "public-legacy-test"


def test_demo_runs_offline_and_is_idempotent(tmp_path):
    first = run_demo(tmp_path)
    second = run_demo(tmp_path)
    assert first == second
    assert first["fixture_version"] == 1
    assert first["integrity"] == "pass"
    assert len(first["categories"]) == 8
    assert "unknown" in first["categories"]
    assert first["domains"]["public-fixtures"]["documents"] == 12
    assert first["domains"]["internal-fixtures"]["documents"] == 1
    assert first["checks"] and set(first["checks"].values()) == {"pass"}


def build_legacy_batch(tmp_path, source_id, locator, *, internal_trace=False):
    artifacts = ArtifactStore(tmp_path / "originals")
    provenance = ProvenanceStore(tmp_path / "events", artifacts)
    adapter = LocalDocumentAdapter(artifacts, provenance)
    pipeline = OfflinePipeline(artifacts, adapter)
    request = DocumentRequest(FIXTURE, source_id, "fixture-key", locator)
    rights = RecordRights("synthetic-fixture")
    if internal_trace:
        trace = InternalIntakeTrace(
            provider_ref="fixture-provider",
            authorization_ref="fixture-approval",
            operation="internal_import",
            format="html",
            expires_at="2099-01-01T00:00:00+00:00",
            allow_read=True,
            allow_store=True,
            allow_extract=True,
            access_basis="synthetic-fixture",
            reuse="unknown",
        )
        with FIXTURE.open("rb") as stream:
            acquired = adapter.acquire_snapshot(
                request,
                stream=stream,
                media_type="text/html",
                expected_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                trace=trace,
            )
        result = pipeline.process_acquired(acquired, rights=rights)
    else:
        result = pipeline.process(request, rights=rights)
    validate_record(result.record)
    assert result.record["document_id"] == document_id(request.source_id, request.logical_key)
    manifest_path = export_batch([result], tmp_path / "batches", provenance)
    assert verify_batch(manifest_path, provenance).valid
    return manifest_path, provenance, result


@pytest.fixture
def published_legacy_batch(tmp_path):
    return build_legacy_batch(tmp_path, "fixture-source", LOCATOR)


def add_target(scope, result, *, domain=DOMAIN, rendition_id="fixture-html"):
    doc = Document(domain, "catalog-fixture")
    revision = Revision(domain, "fixture-revision", doc.id, "observed-a", "2026-11-24T04:00:00Z")
    source = Source(domain, "fixture-provider", "Imaginary Archive", "manual_import")
    item = SourceItem(
        domain,
        "fixture-item",
        source.id,
        result.request.logical_key,
        doc.id,
        result.request.locator,
    )
    rendition = Rendition(
        domain,
        rendition_id,
        doc.id,
        revision.id,
        "html",
        source_item_id=item.id,
        sha256=result.record["original"]["sha256"],
        byte_size=result.record["original"]["byte_length"],
    )
    scope.write(doc, source, item, revision, rendition)
    return doc, item, rendition


def test_links_one_verified_legacy_record_without_changing_pipeline_files(
    tmp_path, published_legacy_batch
):
    manifest_path, provenance, result = published_legacy_batch
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest["records"][0]
    paths = [
        manifest_path,
        manifest_path.parent / entry["record_path"],
        provenance.root / f"{entry['event_id']}.json",
        provenance.artifacts.root / entry["original_reference"],
        FIXTURE,
    ]
    unchanged = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

    with Catalog(tmp_path / "catalog") as catalog:
        catalog.create_domain(AccessDomain(DOMAIN))
        scope = catalog.domain(DOMAIN)
        doc, item, rendition = add_target(scope, result)
        identifiers = {"input_index": 0, "source_item_id": item.id, "rendition_id": rendition.id}
        reference = scope.link_verified_record(manifest_path, provenance, **identifiers)
        assert scope.link_verified_record(manifest_path, provenance, **identifiers) == reference
        assert scope.list(LegacyReference) == (reference,)
        assert scope.legacy_references(result.record["document_id"]) == (reference,)
        assert scope.legacy_references(result.record["document_id"], after=reference.id) == ()
        assert scope.get(Document, doc.id).category == "unknown"
        assert reference.document_id == doc.id
        assert reference.legacy_document_id == result.record["document_id"]
        assert reference.batch_id == manifest["batch_id"]
        assert reference.event_id == entry["event_id"]
        assert reference.record_sha256 == entry["record_sha256"]
        assert reference.original_sha256 == entry["original_sha256"]
        catalog.verify()

    assert verify_batch(manifest_path, provenance).valid
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths} == unchanged


def test_legacy_link_rejects_mismatched_rendition_and_tampered_batch(
    tmp_path, published_legacy_batch
):
    manifest_path, provenance, result = published_legacy_batch
    with Catalog(tmp_path / "catalog") as catalog:
        catalog.create_domain(AccessDomain(DOMAIN))
        scope = catalog.domain(DOMAIN)
        _, item, rendition = add_target(scope, result)
        incorrect = replace(rendition, id="different-bytes", sha256="0" * 64)
        scope.write(incorrect)
        with pytest.raises(CatalogError, match="^legacy_binding_mismatch$"):
            scope.link_verified_record(
                manifest_path,
                provenance,
                input_index=0,
                source_item_id=item.id,
                rendition_id=incorrect.id,
            )
        with pytest.raises(CatalogError, match="^legacy_entry_not_found$"):
            scope.link_verified_record(
                manifest_path,
                provenance,
                input_index=1,
                source_item_id=item.id,
                rendition_id=rendition.id,
            )

        original = provenance.artifacts.root / result.record["original"]["reference"]
        original.write_bytes(b"synthetic tampering")
        with pytest.raises(CatalogError, match="^legacy_batch_invalid$"):
            scope.link_verified_record(
                manifest_path,
                provenance,
                input_index=0,
                source_item_id=item.id,
                rendition_id=rendition.id,
            )
        assert scope.list(LegacyReference) == ()


@pytest.mark.parametrize(
    ("visibility", "source_id", "locator", "internal_trace", "allowed"),
    [
        ("public", "fixture-source", LOCATOR, True, False),
        ("internal", "internal-fixture", "internal:fixture-item", False, False),
        ("internal", "internal-fixture", "internal:fixture-item", True, True),
    ],
)
def test_legacy_binding_enforces_internal_provenance_trace(
    tmp_path, visibility, source_id, locator, internal_trace, allowed
):
    manifest_path, provenance, result = build_legacy_batch(
        tmp_path, source_id, locator, internal_trace=internal_trace
    )
    with Catalog(tmp_path / "catalog") as catalog:
        catalog.create_domain(AccessDomain("test-boundary", visibility=visibility))
        scope = catalog.domain("test-boundary")
        _, item, rendition = add_target(scope, result, domain="test-boundary")
        identifiers = {"input_index": 0, "source_item_id": item.id, "rendition_id": rendition.id}
        if allowed:
            reference = scope.link_verified_record(manifest_path, provenance, **identifiers)
            catalog.create_domain(AccessDomain("separate-public"))
            assert (
                catalog.domain("separate-public").legacy_references(reference.legacy_document_id)
                == ()
            )
        else:
            with pytest.raises(CatalogError, match="^legacy_binding_mismatch$"):
                scope.link_verified_record(manifest_path, provenance, **identifiers)
            assert scope.legacy_references(result.record["document_id"]) == ()
