import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace

import pytest

from medical_data_crawler import export
from medical_data_crawler.backfill_cli import main, read_inputs
from medical_data_crawler.catalog import Catalog, Document, LegacyReference, Rendition
from medical_data_crawler.catalog import store as catalog_store
from medical_data_crawler.catalog.backfill import MAX_ITEMS, BackfillService, Mapping
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore
from scripts.demo_backfill import DOMAIN, build_demo, run_demo


@pytest.fixture
def fixture(tmp_path):
    spec = build_demo(tmp_path)
    provenance = ProvenanceStore(tmp_path / "events", ArtifactStore(tmp_path / "originals"))
    with Catalog(tmp_path / "catalog") as catalog:
        scope = catalog.domain(DOMAIN)
        yield tmp_path, catalog, scope, provenance, tuple(read_inputs(spec))


def execute(fixture, *, dry_run=False, batches=None):
    _, _, scope, provenance, defaults = fixture
    return list(
        BackfillService(scope, provenance).run(
            defaults if batches is None else batches, dry_run=dry_run
        )
    )


def test_mixed_batches_versions_duplicate_hashes_and_immutable_legacy(fixture):
    root, catalog, scope, provenance, batches = fixture
    paths = [
        p
        for folder in ("events", "originals", "batches")
        for p in (root / folder).rglob("*")
        if p.is_file()
    ]
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    reports = execute(fixture)
    assert [r["counts"]["linked"] for r in reports] == [3, 3]
    assert all(r["counts"]["skipped"] == 1 for r in reports)
    references = scope.list(LegacyReference)
    assert len(references) == 6
    assert len({r.original_sha256 for r in references}) == 2
    assert {r.document_id for r in references} == {"document-a", "document-b"}
    assert len(scope.revisions("document-a")) == 2
    assert all(
        doc.category == "unknown" and doc.policy_ref_id is None for doc in scope.list(Document)
    )
    assert all(export.verify_batch(b.manifest_path, provenance).valid for b in batches)
    assert all(r["counts"]["already_linked"] == 3 for r in execute(fixture))
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths} == before
    catalog.verify()


def test_dry_run_no_writes_even_opening_cli(fixture, capsys):
    root, _, scope, _, _ = fixture
    database = root / "catalog/catalog.sqlite3"
    before = database.read_bytes(), database.stat().st_mtime_ns
    reports = execute(fixture, dry_run=True)
    assert reports == execute(fixture, dry_run=True)
    assert all(r["reasons"]["would_link"] == 3 for r in reports)
    assert scope.list(LegacyReference) == ()
    assert (
        main(
            [
                "--catalog",
                str(database.parent),
                "--domain",
                DOMAIN,
                "--events",
                str(root / "events"),
                "--originals",
                str(root / "originals"),
                "--inputs",
                str(root / "inputs.jsonl"),
            ]
        )
        == 0
    )
    assert (database.read_bytes(), database.stat().st_mtime_ns) == before
    assert "would_link" in capsys.readouterr().out


def test_mapping_missing_duplicate_conflicting_and_absent_reference(fixture):
    *_, batches = fixture
    first = batches[0]
    mappings = (
        first.mappings[0],
        first.mappings[0],
        Mapping(10, "legacy-web", "item-legacy-web", "rendition-0-0"),
    )
    report = execute(fixture, batches=[replace(first, mappings=mappings)])[0]
    assert report["reasons"] == {
        "mapping_conflict": 1,
        "mapping_missing": 2,
        "legacy_omission": 1,
        "reference_missing": 1,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("legacy_source_id", "wrong-source"),
        ("source_item_id", "missing-item"),
        ("rendition_id", "missing-rendition"),
    ],
)
def test_mismatched_bindings(fixture, field, value):
    *_, batches = fixture
    first = batches[0]
    mapping = replace(first.mappings[0], **{field: value})
    report = execute(fixture, batches=[replace(first, mappings=(mapping,))])[0]
    assert report["items"][0]["status"] == "needs_review"
    assert report["items"][0]["code"] in {"source_binding_mismatch", "legacy_binding_mismatch"}


@pytest.mark.parametrize("target", ["manifest", "record", "event", "original", "missing_event"])
def test_corruption_blocks_entire_batch(fixture, target):
    _, _, scope, provenance, batches = fixture
    first = batches[0]
    manifest = json.loads(first.manifest_path.read_bytes())
    entry = manifest["records"][0]
    paths = {
        "manifest": first.manifest_path,
        "record": first.manifest_path.parent / entry["record_path"],
        "event": provenance.root / f"{entry['event_id']}.json",
        "missing_event": provenance.root / f"{entry['event_id']}.json",
        "original": provenance.artifacts.root / entry["original_sha256"],
    }
    if target == "missing_event":
        paths[target].unlink()
    else:
        paths[target].write_bytes(b"corrupt synthetic data")
    report = execute(fixture, batches=[first])[0]
    assert report["verification"] == "failed"
    assert scope.list(LegacyReference) == ()


def test_domain_rejection_and_reports_do_not_leak(fixture, caplog):
    root, _, scope, provenance, batches = fixture
    report = execute(fixture, batches=[replace(batches[0], domain_id="private-domain")])[0]
    assert report["batch_code"] == "domain_mismatch"
    encoded = json.dumps(report) + caplog.text
    for secret in (str(root), "private-domain", "Invented", "https://example.org"):
        assert secret not in encoded
    assert scope.list(LegacyReference) == ()
    # Same domain name cannot override the visibility of the trusted catalog handle.
    from medical_data_crawler.catalog import AccessDomain

    with Catalog(root / "internal-catalog") as catalog:
        catalog.create_domain(AccessDomain(DOMAIN, "internal"))
        internal = BackfillService(catalog.domain(DOMAIN), provenance)
        report = next(internal.run([batches[0]], dry_run=False))
        assert report["counts"]["linked"] == 0


@pytest.mark.parametrize("boundary", ["before_insert", "after_insert", "after_commit"])
def test_fault_boundaries_rollback_and_resume(fixture, monkeypatch, boundary):
    _, catalog, scope, _, batches = fixture
    first = replace(batches[0], mappings=(batches[0].mappings[0],))
    original = scope._put
    transaction = catalog_store._write_transaction
    if boundary == "after_commit":

        @contextmanager
        def fault(connection):
            with transaction(connection):
                yield
            raise RuntimeError("confidential fault detail")

        monkeypatch.setattr(catalog_store, "_write_transaction", fault)
    else:

        def fault(record):
            if boundary == "after_insert":
                original(record)
            raise RuntimeError("confidential fault detail")

        monkeypatch.setattr(scope, "_put", fault)
    report = execute(fixture, batches=[first])[0]
    assert report["items"][0]["code"] == "publication_failed"
    assert len(scope.list(LegacyReference)) == (1 if boundary == "after_commit" else 0)
    monkeypatch.undo()
    report = execute(fixture, batches=[first])[0]
    assert report["items"][0]["status"] == (
        "already_linked" if boundary == "after_commit" else "linked"
    )
    catalog.verify()


def test_limits_and_lazy_corpus_processing(fixture):
    *_, batches = fixture
    consumed = []

    def corpus():
        for i in range(2000):
            consumed.append(i)
            yield batches[0]

    _, _, scope, provenance, _ = fixture
    reports = BackfillService(scope, provenance).run(corpus())
    assert next(reports)["verification"] == "pass"
    assert consumed == [0]
    mappings = (batches[0].mappings[0] for _ in range(MAX_ITEMS + 10000))
    report = execute(fixture, batches=[replace(batches[0], mappings=mappings)])[0]
    assert report["batch_code"] == "mapping_size_limit"


def test_verifier_bounded_reads(fixture):
    *_, provenance, batches = fixture
    result = export.verify_batch(batches[0].manifest_path, provenance, max_file_bytes=20)
    assert not result.valid and result.error_code == "verification_size_limit"


def test_existing_link_never_reassigned(fixture):
    _, _, scope, _, batches = fixture
    execute(fixture, batches=[batches[0]])
    rendition = scope.get(Rendition, "rendition-0-0")
    scope.write(replace(rendition, id="alternate-rendition"))
    mapping = replace(batches[0].mappings[0], rendition_id="alternate-rendition")
    report = execute(fixture, batches=[replace(batches[0], mappings=(mapping,))])[0]
    assert report["items"][0]["code"] == "record_conflict"
    assert len(scope.list(LegacyReference)) == 3


def test_demo_runs_twice_offline(tmp_path, capsys):
    run_demo(tmp_path)
    run_demo(tmp_path)
    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert reports[-1]["counts"]["already_linked"] == 3


def test_conflicting_document_owners_rejected_before_publication(fixture):
    from medical_data_crawler.catalog import SourceItem

    _, _, scope, _, batches = fixture
    # Duplicate a verified record into a new batch, with two explicit competing targets.
    source = scope.get(SourceItem, "item-legacy-web")
    rendition = scope.get(Rendition, "rendition-0-0")
    from medical_data_crawler.catalog import Revision

    scope.write(
        Document(DOMAIN, "competing-document"),
        replace(
            source,
            id="competing-item",
            native_key="competing-key",
            document_id="competing-document",
        ),
        Revision(
            DOMAIN, "competing-revision", "competing-document", "unknown", "2026-11-24T00:00:00Z"
        ),
        replace(
            rendition,
            id="competing-rendition",
            document_id="competing-document",
            revision_id="competing-revision",
            source_item_id="competing-item",
        ),
    )
    # The same legacy document can occur twice; SHA/URL equality is not an identity decision.
    batch = batches[0]
    manifest = json.loads(batch.manifest_path.read_bytes())
    record = manifest["records"][0]
    record2 = {**record, "input_index": 2, "record_path": "records/2.json"}
    (batch.manifest_path.parent / "records/2.json").write_bytes(
        (batch.manifest_path.parent / "records/0.json").read_bytes()
    )
    manifest["records"][2] = record2
    manifest["summary"] = export._summary(manifest["records"], manifest["omissions"])
    batch.manifest_path.write_bytes(export._json_bytes(manifest))
    batch = replace(
        batch,
        manifest_sha256=hashlib.sha256(batch.manifest_path.read_bytes()).hexdigest(),
        mappings=(
            batch.mappings[0],
            Mapping(2, "legacy-web", "competing-item", "competing-rendition"),
        ),
    )
    report = execute(fixture, batches=[batch])[0]
    assert report["reconciliation"]["conflicts"] == 2
    assert scope.list(LegacyReference) == ()


def test_large_synthetic_batch_is_bounded(fixture):
    import tracemalloc

    from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
    from medical_data_crawler.catalog.backfill import BatchInput
    from medical_data_crawler.pipeline import OfflinePipeline, RecordRights

    root, _, scope, provenance, batches = fixture
    pipeline = OfflinePipeline(
        provenance.artifacts, LocalDocumentAdapter(provenance.artifacts, provenance)
    )
    result = pipeline.process(
        DocumentRequest(
            root / "invented.html", "legacy-web", "stable-key", "https://example.org/legacy-web"
        ),
        rights=RecordRights("synthetic-fixture"),
    )
    manifest = export.export_batch((result for _ in range(MAX_ITEMS)), root / "large", provenance)
    batch = BatchInput(
        manifest,
        hashlib.sha256(manifest.read_bytes()).hexdigest(),
        DOMAIN,
        tuple(replace(batches[0].mappings[0], input_index=i) for i in range(MAX_ITEMS)),
    )
    tracemalloc.start()
    try:
        report = next(BackfillService(scope, provenance).run([batch]))
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert report["reasons"] == {"would_link": MAX_ITEMS}
    assert peak < 24 * 1024 * 1024
    manifest = export.export_batch(
        (result for _ in range(MAX_ITEMS + 1)), root / "large", provenance
    )
    report = execute(
        fixture,
        batches=[
            replace(
                batch,
                manifest_path=manifest,
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            )
        ],
    )[0]
    assert report["batch_code"] == "batch_size_limit"


def test_internal_records_never_enter_public_catalog(fixture, caplog):
    from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
    from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
    from medical_data_crawler.provenance import InternalIntakeTrace

    root, _, scope, provenance, batches = fixture
    adapter = LocalDocumentAdapter(provenance.artifacts, provenance)
    request = DocumentRequest(
        root / "invented.html", "internal-fixture", "neutral-key", "internal:confidential"
    )
    trace = InternalIntakeTrace(
        "provider",
        "approval",
        "internal_import",
        "html",
        "2099-01-01T00:00:00Z",
        True,
        True,
        True,
        "fixture",
        "unknown",
    )
    with request.path.open("rb") as stream:
        acquired = adapter.acquire_snapshot(
            request,
            stream=stream,
            media_type="text/html",
            expected_sha256=hashlib.sha256(request.path.read_bytes()).hexdigest(),
            trace=trace,
        )
    result = OfflinePipeline(provenance.artifacts, adapter).process_acquired(
        acquired, rights=RecordRights("fixture")
    )
    manifest = export.export_batch([result], root / "private-batches", provenance)
    mapping = replace(batches[0].mappings[0], legacy_source_id="internal-fixture")
    batch = replace(
        batches[0],
        manifest_path=manifest,
        mappings=(mapping,),
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )
    report = execute(fixture, batches=[batch])[0]
    assert report["items"][0]["code"] == "legacy_binding_mismatch"
    assert scope.list(LegacyReference) == ()
    serialized = json.dumps(report) + caplog.text
    for secret in (
        "confidential",
        "internal-fixture",
        acquired.artifact.sha256,
        acquired.event_id,
        str(root),
    ):
        assert secret not in serialized
    # The trusted internal handle can attach the same verified evidence privately.
    from medical_data_crawler.catalog import AccessDomain, Revision, Source, SourceItem

    with Catalog(root / "private-catalog") as catalog:
        domain = "private-fixture"
        catalog.create_domain(AccessDomain(domain, "internal"))
        private = catalog.domain(domain)
        private.write(
            Source(domain, "private-provider", "Fixture provider", "internal_handoff"),
            Document(domain, "private-document"),
            SourceItem(
                domain,
                "private-item",
                "private-provider",
                "reviewed-key",
                "private-document",
                request.locator,
            ),
            Revision(
                domain, "private-revision", "private-document", "unknown", "2026-11-24T00:00:00Z"
            ),
            Rendition(
                domain,
                "private-html",
                "private-document",
                "private-revision",
                "html",
                source_item_id="private-item",
                sha256=acquired.artifact.sha256,
                byte_size=acquired.artifact.byte_size,
            ),
        )
        private_batch = replace(
            batch,
            domain_id=domain,
            mappings=(Mapping(0, "internal-fixture", "private-item", "private-html"),),
        )
        report = next(BackfillService(private, provenance).run([private_batch], dry_run=False))
        assert report["counts"]["linked"] == 1
        assert private.list(LegacyReference)[0].locator == request.locator
        assert scope.list(LegacyReference) == ()
        catalog.verify()


@pytest.mark.parametrize("target", ["manifest", "record", "event", "original"])
def test_changed_evidence_after_planning_is_not_published(fixture, monkeypatch, target):
    _, _, scope, provenance, batches = fixture
    batch = replace(batches[0], mappings=(batches[0].mappings[0],))
    manifest = json.loads(batch.manifest_path.read_bytes())
    entry = manifest["records"][0]
    paths = {
        "manifest": batch.manifest_path,
        "record": batch.manifest_path.parent / entry["record_path"],
        "event": provenance.root / f"{entry['event_id']}.json",
        "original": provenance.artifacts.root / entry["original_sha256"],
    }
    original = scope._link_legacy

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get("dry_run"):
            paths[target].write_bytes(b"synthetic mutation after plan")
        return result

    monkeypatch.setattr(scope, "_link_legacy", changed)
    report = execute(fixture, batches=[batch])[0]
    assert report["items"][0]["status"] == "failed"
    assert scope.list(LegacyReference) == ()


def test_process_interruption_rolls_back_uncommitted_item(fixture, monkeypatch):
    _, catalog, scope, _, batches = fixture
    original = scope._put

    def interrupted(record):
        original(record)
        raise KeyboardInterrupt

    monkeypatch.setattr(scope, "_put", interrupted)
    with pytest.raises(KeyboardInterrupt):
        execute(fixture, batches=[batches[0]])
    assert scope.list(LegacyReference) == ()
    monkeypatch.undo()
    assert execute(fixture, batches=[batches[0]])[0]["counts"]["linked"] == 3
    catalog.verify()


def test_network_paths_rejected_before_read(fixture):
    from pathlib import Path

    *_, batches = fixture
    report = execute(
        fixture,
        batches=[
            replace(batches[0], manifest_path=Path("//forbidden-server/secret/manifest.json"))
        ],
    )[0]
    assert report["batch_code"] == "manifest_path_invalid"


def test_cli_rejects_oversized_or_malformed_envelopes(tmp_path):
    from medical_data_crawler.catalog import CatalogError
    from medical_data_crawler.catalog.backfill import MAX_MANIFEST_BYTES

    path = tmp_path / "malformed.jsonl"
    path.write_text('{"backfill_version":"0.1"}\n')
    with pytest.raises(CatalogError, match="^mapping_invalid$"):
        tuple(read_inputs(path))
    path.write_bytes(b"x" * (MAX_MANIFEST_BYTES + 1))
    with pytest.raises(CatalogError, match="^mapping_size_limit$"):
        tuple(read_inputs(path))
