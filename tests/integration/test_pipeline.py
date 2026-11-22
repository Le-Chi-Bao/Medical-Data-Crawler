import hashlib
import json
from pathlib import Path

import pytest

from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
from medical_data_crawler.contract import validate_record
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore

FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic.html"
RIGHTS = RecordRights("Self-authored synthetic test fixture")


@pytest.fixture
def pipeline(tmp_path):
    artifacts = ArtifactStore(tmp_path / "originals")
    provenance = ProvenanceStore(tmp_path / "events", artifacts)
    return OfflinePipeline(artifacts, LocalDocumentAdapter(artifacts, provenance))


def request(path, *, source="synthetic", key="fixture-1"):
    return DocumentRequest(path, source, key, "safe-local-fixture")


def test_end_to_end_original_and_provenance_are_verifiable(pipeline):
    before = FIXTURE.read_bytes()
    mtime = FIXTURE.stat().st_mtime_ns
    result = pipeline.process(request(FIXTURE), rights=RIGHTS)
    assert result.errors == ()
    assert result.extraction.status == "success"
    validate_record(result.record)
    original = result.record["original"]
    assert original["sha256"] == hashlib.sha256(before).hexdigest()
    assert original["byte_length"] == len(before)
    assert (pipeline.artifacts.root / original["reference"]).read_bytes() == before
    assert FIXTURE.read_bytes() == before
    assert FIXTURE.stat().st_mtime_ns == mtime
    event_id = result.acquisition.event_id
    event = json.loads(
        (pipeline.acquisition.provenance.root / f"{event_id}.json").read_text("utf-8")
    )
    assert event["document_id"] == result.record["document_id"]
    assert event["sha256"] == original["sha256"]
    assert event["acquired_at"] == result.record["source"]["acquired_at"]
    assert result.record["source"]["context"] == f"provenance_event:{event_id}"
    assert result.record["rights"]["reuse"] == "unknown"
    assert result.record["scope"] == result.record["audience"] == "unknown"


def test_reruns_and_identical_bytes_across_sources(pipeline):
    first = pipeline.process(request(FIXTURE), rights=RIGHTS)
    second = pipeline.process(request(FIXTURE), rights=RIGHTS)
    other = pipeline.process(request(FIXTURE, source="other"), rights=RIGHTS)
    assert first.acquisition.artifact == second.acquisition.artifact == other.acquisition.artifact
    assert first.extraction == second.extraction
    assert first.record["document_id"] == second.record["document_id"]
    assert first.record["document_id"] != other.record["document_id"]
    assert len(list(pipeline.artifacts.root.iterdir())) == 1
    assert len(list(pipeline.acquisition.provenance.root.glob("*.json"))) == 3


def test_changed_content_keeps_identity_and_both_originals(pipeline, tmp_path):
    path = tmp_path / "versioned.html"
    path.write_bytes(b"<p>First</p>")
    first = pipeline.process(request(path), rights=RIGHTS)
    path.write_bytes(b"<p>Second</p>")
    second = pipeline.process(request(path), rights=RIGHTS)
    assert first.record["document_id"] == second.record["document_id"]
    assert first.acquisition.artifact != second.acquisition.artifact
    assert len(list(pipeline.artifacts.root.iterdir())) == 2
    assert (
        pipeline.artifacts.root / first.acquisition.artifact.reference
    ).read_bytes() == b"<p>First</p>"


def test_mixed_batch_isolates_failures(pipeline, tmp_path, pdf_bytes):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 corrupt")
    empty = tmp_path / "empty.html"
    empty.write_bytes(b" ")
    unsupported = tmp_path / "input.txt"
    unsupported.write_bytes(b"fixture")
    pdf = tmp_path / "valid.pdf"
    pdf.write_bytes(pdf_bytes([[(72, 720, "Synthetic PDF")]]))
    paths = [FIXTURE, tmp_path / "missing.html", broken, empty, unsupported, pdf]
    results = pipeline.process_many(
        [request(p, key=str(i)) for i, p in enumerate(paths)], rights=RIGHTS
    )
    assert [r.extraction.status if r.extraction else None for r in results] == [
        "success",
        None,
        "failed",
        "failed",
        None,
        "success",
    ]
    for index in [0, 2, 3, 5]:
        validate_record(results[index].record)
    for index in [2, 3]:
        assert results[index].record["content"] == []
        assert results[index].record["extraction"]["errors"]
    assert results[1].record is None and results[4].record is None
    assert len(list(pipeline.acquisition.provenance.root.glob("*.json"))) == len(paths)


def test_missing_rights_keeps_internal_result_without_inventing_record(pipeline):
    result = pipeline.process(request(FIXTURE))
    assert result.extraction.status == "success"
    assert result.record is None
    assert "record_not_built_missing_rights" in result.warnings
    assert result.errors == ()


def test_unknown_rights_do_not_allow_distribution_and_restricted_requires_evidence(pipeline):
    result = pipeline.process(request(FIXTURE), rights=RecordRights("Explicit fixture access"))
    assert result.record["rights"] == dict(
        access_basis="Explicit fixture access", reuse="unknown", evidence=None
    )
    for reuse in ["permitted", "restricted"]:
        missing = pipeline.process(request(FIXTURE), rights=RecordRights("Fixture access", reuse))
        assert missing.record is None
        assert "record_validation_error" in missing.errors
        backed = pipeline.process(
            request(FIXTURE), rights=RecordRights("Fixture access", reuse, "Fixture evidence")
        )
        validate_record(backed.record)


def test_pdf_partial_errors_and_page_boundaries_are_kept(pipeline, tmp_path, pdf_bytes):
    path = tmp_path / "partial.pdf"
    path.write_bytes(
        pdf_bytes([[(72, 720, "First")], b"BT (unterminated", None, [(72, 720, "Last")]])
    )
    result = pipeline.process(request(path), rights=RIGHTS)
    validate_record(result.record)
    assert result.record["extraction"]["status"] == "partial"
    assert result.record["extraction"]["errors"] == list(result.extraction.errors)
    assert set(result.extraction.warnings) <= set(result.record["extraction"]["warnings"])
    assert "v0.1_page_boundaries_internal_only" in result.record["extraction"]["warnings"]
    assert result.extraction.page_count == 4
    assert [p.status for p in result.extraction.pages] == [
        "success",
        "failed",
        "no_text",
        "success",
    ]


def test_scan_like_pdf_is_a_valid_failed_record(pipeline, tmp_path, image_only_pdf):
    path = tmp_path / "no-text.pdf"
    path.write_bytes(image_only_pdf)
    result = pipeline.process(request(path), rights=RIGHTS)
    validate_record(result.record)
    assert result.record["extraction"]["status"] == "failed"
    assert result.record["content"] == []
    assert result.acquisition.accepted


def test_extraction_reads_artifact_even_when_source_changes(pipeline, tmp_path, monkeypatch):
    path = tmp_path / "source.html"
    path.write_bytes(b"<p>Original</p>")
    acquire = pipeline.acquisition.acquire

    def acquire_then_change(req):
        acquired = acquire(req)
        path.write_bytes(b"<p>Changed externally after acquisition</p>")
        return acquired

    monkeypatch.setattr(pipeline.acquisition, "acquire", acquire_then_change)
    result = pipeline.process(request(path), rights=RIGHTS)
    assert result.record["content"][0]["text"] == "Original"


def test_corrupt_artifact_is_reported_without_success_record(pipeline, tmp_path, monkeypatch):
    acquire = pipeline.acquisition.acquire

    def corrupt_after_acquisition(req):
        acquired = acquire(req)
        (pipeline.artifacts.root / acquired.artifact.reference).write_bytes(b"external corruption")
        return acquired

    monkeypatch.setattr(pipeline.acquisition, "acquire", corrupt_after_acquisition)
    result = pipeline.process(request(FIXTURE), rights=RIGHTS)
    assert result.record is None and result.extraction is None
    assert result.errors == ("artifact_read_error",)
    assert result.acquisition.event_id
    assert (
        pipeline.artifacts.root / result.acquisition.artifact.reference
    ).read_bytes() == b"external corruption"


def test_pdf_signature_overrides_html_suffix_with_warning(pipeline, tmp_path, pdf_bytes):
    path = tmp_path / "actually-pdf.html"
    path.write_bytes(pdf_bytes([[(72, 720, "Fixture")]]))
    result = pipeline.process(request(path), rights=RIGHTS)
    validate_record(result.record)
    assert result.extraction.document_type == "pdf"
    assert result.record["original"]["media_type"] == "application/pdf"
    assert "format_extension_mismatch" in result.record["extraction"]["warnings"]


def test_binary_masquerading_as_html_does_not_become_text(pipeline, tmp_path):
    path = tmp_path / "binary.html"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\x00synthetic")
    result = pipeline.process(request(path), rights=RIGHTS)
    validate_record(result.record)
    assert result.record["extraction"]["status"] == "failed"
    assert result.errors == ("unsupported_content_format",)


def test_unexpected_extractor_error_does_not_stop_batch(pipeline, monkeypatch):
    def fail(data):
        raise RuntimeError("secret fixture text")

    monkeypatch.setattr(pipeline.extractors["text/html"], "extract", fail)
    results = pipeline.process_many([request(FIXTURE), request(FIXTURE)], rights=RIGHTS)
    for result in results:
        validate_record(result.record)
        assert result.record["extraction"]["status"] == "failed"
        assert result.errors == ("extractor_unexpected_error",)
        assert "secret" not in repr(result.errors)


def test_unexpected_acquisition_error_does_not_stop_batch(pipeline, monkeypatch):
    acquire = pipeline.acquisition.acquire
    calls = 0

    def fail_once(req):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("secret")
        return acquire(req)

    monkeypatch.setattr(pipeline.acquisition, "acquire", fail_once)
    first, second = pipeline.process_many([request(FIXTURE), request(FIXTURE)], rights=RIGHTS)
    assert first.record is None
    assert first.errors == ("acquisition_unexpected_error",)
    assert second.extraction.status == "success"
