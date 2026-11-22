import hashlib
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from medical_data_crawler import export
from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
from medical_data_crawler.contract import validate_record
from medical_data_crawler.export import ExportError, export_batch, validate_manifest, verify_batch
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic.html"
RIGHTS = RecordRights("Synthetic fixture")


@pytest.fixture
def workspace(tmp_path):
    artifacts = ArtifactStore(tmp_path / "originals")
    provenance = ProvenanceStore(tmp_path / "events", artifacts)
    pipeline = OfflinePipeline(artifacts, LocalDocumentAdapter(artifacts, provenance))
    return pipeline, provenance, tmp_path / "exports"


def document(path=FIXTURE, *, source="fixture"):
    return DocumentRequest(path, source, "local-test", "fixture:synthetic")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_mixed_html_pdf_batch_preserves_records_and_checksums(workspace, tmp_path, pdf_bytes):
    pipeline, provenance, output = workspace
    partial = tmp_path / "partial.pdf"
    partial.write_bytes(pdf_bytes([[(72, 700, "Synthetic text")], None]))
    blank = tmp_path / "blank.pdf"
    blank.write_bytes(pdf_bytes([None]))
    missing = tmp_path / "missing.html"
    results = pipeline.process_many(
        [document(), document(missing), document(partial), document(blank)], rights=RIGHTS
    )
    skipped = pipeline.process(document())
    invalid = pipeline.process(document(), rights=RecordRights(" "))
    snapshots = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for store in (provenance, pipeline.artifacts)
        for path in store.root.iterdir()
    }

    manifest_path = export_batch([*results, skipped, invalid], output, provenance)
    manifest = load(manifest_path)
    validate_manifest(manifest)
    assert datetime.fromisoformat(manifest["created_at"]).utcoffset() is not None
    assert manifest["summary"] == {
        "total": 6,
        "exported": 3,
        "failed": 2,
        "skipped": 1,
        "extraction": {"success": 1, "partial": 1, "failed": 1},
    }
    assert [item["code"] for item in manifest["omissions"]] == [
        "acquisition_failed",
        "missing_access_basis",
        "record_validation_error",
    ]
    failed_event = manifest["omissions"][0]["event_id"]
    assert failed_event == results[1].acquisition.event_id
    assert load(provenance.root / f"{failed_event}.json")["status"] == "failed"
    assert {path.name for path in (manifest_path.parent / "records").iterdir()} == {
        "0.json",
        "2.json",
        "3.json",
    }

    for entry in manifest["records"]:
        index = entry["input_index"]
        record_path = manifest_path.parent / entry["record_path"]
        payload = record_path.read_bytes()
        record = load(record_path)
        validate_record(record)
        assert record == results[index].record
        assert entry["record_sha256"] == hashlib.sha256(payload).hexdigest()
        assert entry["record_byte_size"] == len(payload)
        original = pipeline.artifacts.root / entry["original_reference"]
        assert entry["original_sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
        assert original.stat().st_size == record["original"]["byte_length"]
        assert entry["reuse"] == "unknown"
        assert entry["extraction_status"] == record["extraction"]["status"]
    assert b"\xef\xbb\xbf" not in (manifest_path.parent / "records/0.json").read_bytes()[:3]
    assert "Tổn thương da".encode() in (manifest_path.parent / "records/0.json").read_bytes()
    assert verify_batch(manifest_path, provenance).valid
    assert {path.name for path in manifest_path.parent.iterdir()} == {"records", "manifest.json"}
    assert all(
        (path.read_bytes(), path.stat().st_mtime_ns) == snapshot
        for path, snapshot in snapshots.items()
    )


def test_reruns_and_content_versions_preserve_published_batches(workspace, tmp_path, monkeypatch):
    pipeline, provenance, output = workspace
    local = tmp_path / "version.html"
    local.write_bytes(b"<p>First version</p>")
    first, duplicate = pipeline.process_many(
        [document(local), document(local, source="other")], rights=RIGHTS
    )
    first_path = export_batch([first, duplicate], output, provenance)
    first_batch_files = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (first_path, *(first_path.parent / "records").iterdir())
    }
    repeat_path = export_batch([first, duplicate], output, provenance)
    first_manifest = load(first_path)
    first_entries = first_manifest["records"]
    assert first_manifest["batch_id"] != load(repeat_path)["batch_id"]
    assert first_entries == load(repeat_path)["records"]
    assert first_entries[0]["document_id"] != first_entries[1]["document_id"]
    assert first_entries[0]["original_sha256"] == first_entries[1]["original_sha256"]
    assert len(list(pipeline.artifacts.root.iterdir())) == 1

    reacquired = pipeline.process(document(local), rights=RIGHTS)
    reacquired_path = export_batch([reacquired], output, provenance)
    same_document = load(reacquired_path)["records"][0]
    assert same_document["document_id"] == first_entries[0]["document_id"]
    assert same_document["event_id"] != first_entries[0]["event_id"]
    assert same_document["record_sha256"] != first_entries[0]["record_sha256"]
    local.write_bytes(b"<p>Second version</p>")
    changed = pipeline.process(document(local), rights=RIGHTS)
    changed_path = export_batch([changed], output, provenance)
    new_version = load(changed_path)["records"][0]
    assert new_version["document_id"] == same_document["document_id"]
    assert new_version["original_sha256"] != same_document["original_sha256"]
    assert len(list(pipeline.artifacts.root.iterdir())) == 2

    monkeypatch.setattr(export, "uuid4", lambda: UUID(hex=first_manifest["batch_id"]))
    with pytest.raises(ExportError, match="^batch_create_error$"):
        export_batch([changed], output, provenance)
    for manifest in (first_path, repeat_path, reacquired_path, changed_path):
        assert verify_batch(manifest, provenance).valid
    assert all(
        (path.read_bytes(), path.stat().st_mtime_ns) == snapshot
        for path, snapshot in first_batch_files.items()
    )


def test_invalid_record_and_untrusted_identifiers_are_isolated(workspace):
    pipeline, provenance, output = workspace
    # Caller-supplied source and locator can contain filesystem metacharacters.
    request = replace(document(), source_id=r"..\CON", locator="../../outside.json")
    result = pipeline.process(
        request, rights=RecordRights("Fixture", "restricted", "Synthetic evidence")
    )
    invalid = replace(result, record={**result.record, "rights": {}})
    bad_identity = replace(result, record={**result.record, "document_id": "../../../CON"})
    invalid_encoding = replace(
        result,
        record={**result.record, "metadata": {**result.record["metadata"], "title": "\ud800"}},
    )
    path = export_batch([invalid, bad_identity, invalid_encoding, result], output, provenance)
    manifest = load(path)
    assert [item["code"] for item in manifest["omissions"]] == [
        "record_validation_error",
        "provenance_integrity_error",
        "record_encoding_error",
    ]
    entry = manifest["records"][0]
    assert entry["record_path"] == "records/3.json"
    assert entry["reuse"] == "restricted"
    assert load(path.parent / entry["record_path"]) == result.record
    assert "../../outside.json" not in path.read_text(encoding="utf-8")
    assert not (output.parent / "outside.json").exists()
    assert verify_batch(path, provenance).valid


def test_mismatched_event_does_not_attribute_record_to_another_source(workspace):
    pipeline, provenance, output = workspace
    first, other = pipeline.process_many(
        [document(), document(source="other-source")], rights=RIGHTS
    )
    path = export_batch([replace(first, record=other.record), other], output, provenance)
    manifest = load(path)
    assert manifest["omissions"][0]["code"] == "provenance_integrity_error"
    assert manifest["records"][0]["event_id"] == other.acquisition.event_id
    assert verify_batch(path, provenance).valid


@pytest.mark.parametrize(
    ("target", "missing", "code"),
    [
        ("record", True, "record_read_error"),
        ("record", False, "record_integrity_error"),
        ("original", True, "original_integrity_error"),
        ("original", False, "original_integrity_error"),
        ("event", True, "provenance_integrity_error"),
        ("event", False, "provenance_integrity_error"),
    ],
)
def test_verify_detects_tampering_and_missing_files(workspace, target, missing, code):
    pipeline, provenance, output = workspace
    result = pipeline.process(document(), rights=RIGHTS)
    path = export_batch([result], output, provenance)
    entry = load(path)["records"][0]
    targets = {
        "record": path.parent / entry["record_path"],
        "original": pipeline.artifacts.root / entry["original_reference"],
        "event": provenance.root / (entry["event_id"] + ".json"),
    }
    file_path = targets[target]
    if missing:
        file_path.unlink()
    elif target == "event":
        event = load(file_path)
        event["locator"] = "different-fixture"
        file_path.write_text(json.dumps(event), encoding="utf-8")
    else:
        payload = file_path.read_bytes()
        file_path.write_bytes(b" " + payload[1:])
    verification = verify_batch(path, provenance)
    assert not verification.valid
    assert verification.error_code == code
    assert verification.input_index == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("record_path", "../outside.json"),
        ("record_path", r"..\outside.json"),
        ("record_path", "records/1.json"),
        ("record_path", "records/0.json\n"),
        ("record_path", "/records/0.json"),
        ("event_id", "../../untrusted"),
        ("original_reference", "../untrusted"),
        ("input_index", 4),
    ],
)
def test_manifest_rejects_untrusted_references(workspace, field, value):
    pipeline, provenance, output = workspace
    path = export_batch([pipeline.process(document(), rights=RIGHTS)], output, provenance)
    manifest = load(path)
    manifest["records"][0][field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ExportError, match="^manifest_invalid$"):
        validate_manifest(manifest)
    assert verify_batch(path, provenance).error_code == "manifest_invalid"


def test_manifest_rejects_bad_counts_and_timezone(workspace):
    pipeline, provenance, output = workspace
    path = export_batch([], output, provenance)
    manifest = load(path)
    assert manifest["summary"]["total"] == 0
    assert verify_batch(path, provenance).valid
    with pytest.raises(ExportError, match="^manifest_invalid$"):
        validate_manifest({**manifest, "summary": {**manifest["summary"], "total": 1}})
    with pytest.raises(ExportError, match="^manifest_invalid$"):
        validate_manifest({**manifest, "created_at": "2026-11-23T10:15:00"})


def test_missing_original_before_export_is_isolated(workspace, tmp_path):
    pipeline, provenance, output = workspace
    surviving = tmp_path / "surviving.html"
    surviving.write_bytes(b"<p>Survives</p>")
    results = pipeline.process_many([document(), document(surviving)], rights=RIGHTS)
    (pipeline.artifacts.root / results[0].acquisition.artifact.reference).unlink()
    path = export_batch(results, output, provenance)
    manifest = load(path)
    assert manifest["omissions"][0]["code"] == "original_integrity_error"
    assert [item["input_index"] for item in manifest["records"]] == [1]
    assert verify_batch(path, provenance).valid


def test_mid_write_failure_keeps_other_record_and_cleans_pending_files(workspace, monkeypatch):
    pipeline, provenance, output = workspace
    result = pipeline.process(document(), rights=RIGHTS)
    fsync = export.os.fsync
    failed = False

    def fail_once(fd):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("synthetic sensitive detail")
        fsync(fd)

    monkeypatch.setattr(export.os, "fsync", fail_once)
    path = export_batch([result, result], output, provenance)
    manifest = load(path)
    assert manifest["omissions"][0]["code"] == "record_write_error"
    assert [entry["record_path"] for entry in manifest["records"]] == ["records/1.json"]
    assert "synthetic sensitive detail" not in path.read_text(encoding="utf-8")
    assert not list(output.rglob(".pending-*"))
    assert verify_batch(path, provenance).valid


def test_manifest_is_linked_last_and_publish_failure_cleans_batch(workspace, monkeypatch):
    pipeline, provenance, output = workspace
    result = pipeline.process(document(), rights=RIGHTS)
    link = export.os.link
    before = export_batch([result], output, provenance)

    def fail_manifest(source, target):
        assert not (target.parent.parent / "manifest.json").exists()
        if target.name == "manifest.json":
            assert not target.exists()
            entry = load(source)["records"][0]
            assert (target.parent / entry["record_path"]).is_file()
            raise OSError("synthetic manifest link failure")
        link(source, target)

    monkeypatch.setattr(export.os, "link", fail_manifest)
    with pytest.raises(ExportError, match="^batch_write_error$"):
        export_batch([result], output, provenance)
    assert list(output.iterdir()) == [before.parent]
    assert verify_batch(before, provenance).valid


def test_changed_record_before_publication_aborts_entire_batch(workspace):
    pipeline, provenance, output = workspace
    result = pipeline.process(document(), rights=RIGHTS)

    def interrupted_results():
        yield result
        record = next(output.glob("*/records/0.json"))
        assert not (record.parent.parent / "manifest.json").exists()
        record.write_bytes(b"synthetic corruption")
        yield result

    with pytest.raises(ExportError, match="^record_integrity_error$") as error:
        export_batch(interrupted_results(), output, provenance)
    assert error.value.input_index == 0
    assert list(output.iterdir()) == []


@pytest.mark.parametrize("publish_manifest", [False, True])
def test_interrupt_immediately_after_link_preserves_committed_batches(
    workspace, monkeypatch, publish_manifest
):
    pipeline, provenance, output = workspace
    result = pipeline.process(document(), rights=RIGHTS)
    link = export.os.link

    def interrupt_after_link(source, target):
        link(source, target)
        if (target.name == "manifest.json") == publish_manifest:
            raise KeyboardInterrupt

    monkeypatch.setattr(export.os, "link", interrupt_after_link)
    with pytest.raises(KeyboardInterrupt):
        export_batch([result], output, provenance)
    if publish_manifest:
        manifest = next(output.glob("*/manifest.json"))
        assert verify_batch(manifest, provenance).valid
        assert not list(output.rglob(".pending-*"))
    else:
        assert list(output.iterdir()) == []
