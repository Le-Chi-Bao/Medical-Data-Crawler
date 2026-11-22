import json
from pathlib import Path

import pytest

from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
from medical_data_crawler.provenance import ProvenanceError, ProvenanceStore, document_id
from medical_data_crawler.storage import ArtifactStore, StorageError


@pytest.fixture
def adapter(tmp_path):
    artifacts = ArtifactStore(tmp_path / "originals")
    return LocalDocumentAdapter(artifacts, ProvenanceStore(tmp_path / "events", artifacts))


def request(path, source="synthetic"):
    return DocumentRequest(path, source, "doc-1", "safe-fixture")


@pytest.mark.parametrize("extension", ["html", "htm", "HTML", "pdf"])
def test_acquire_bytes_identity_and_rerun(adapter, tmp_path, extension):
    path = tmp_path / f"fixture.{extension}"
    data = b"\x00\xfforiginal\r\n"
    path.write_bytes(data)
    original_mtime = path.stat().st_mtime_ns
    first = adapter.acquire(request(path))
    second = adapter.acquire(request(path))
    other = adapter.acquire(request(path, "other-source"))
    assert first.accepted and second.accepted and other.accepted
    assert first.document_id == second.document_id == document_id("synthetic", "doc-1")
    assert first.document_id != other.document_id
    assert first.artifact == second.artifact == other.artifact
    assert len({first.event_id, second.event_id, other.event_id}) == 3
    assert path.read_bytes() == data
    assert path.stat().st_mtime_ns == original_mtime
    assert len(list(adapter.artifacts.root.iterdir())) == 1
    assert (adapter.artifacts.root / first.artifact.reference).read_bytes() == data
    events = [json.loads(p.read_text("utf-8")) for p in adapter.provenance.root.glob("*.json")]
    assert len(events) == 3
    for event in events:
        assert event["status"] == "accepted"
        assert event["locator"] == "safe-fixture"
        assert event["sha256"] == first.artifact.sha256


@pytest.mark.parametrize(
    ("filename", "data", "error", "event_error"),
    [
        ("missing.html", None, "file_not_found", "read_error"),
        ("empty.pdf", b"", "empty_file", "invalid_input"),
        ("unknown.txt", b"fixture", "unsupported_format", "invalid_input"),
    ],
)
def test_rejected_files_have_failure_events(adapter, tmp_path, filename, data, error, event_error):
    path = tmp_path / filename
    if data is not None:
        path.write_bytes(data)
    result = adapter.acquire(request(path))
    assert not result.accepted
    assert result.artifact is None
    assert result.errors == (error,)
    event = json.loads((adapter.provenance.root / f"{result.event_id}.json").read_text("utf-8"))
    assert event["status"] == "failed"
    assert event["sha256"] is None
    assert event["error_code"] == event_error


def test_read_error_is_safe(adapter, tmp_path, monkeypatch):
    def fail(*args):
        raise PermissionError("secret/path")

    monkeypatch.setattr(Path, "read_bytes", fail)
    result = adapter.acquire(request(tmp_path / "blocked.html"))
    assert result.errors == ("read_error",)
    assert result.event_id is not None
    assert "secret" not in repr(result.errors)


@pytest.mark.parametrize("stage", ["storage", "provenance"])
def test_store_failures_are_reported(adapter, tmp_path, monkeypatch, stage):
    path = tmp_path / "fixture.html"
    path.write_bytes(b"<p>fixture</p>")

    def fail(*args, **kwargs):
        raise StorageError("secret") if stage == "storage" else ProvenanceError("secret")

    target = adapter.artifacts if stage == "storage" else adapter.provenance
    monkeypatch.setattr(target, "put" if stage == "storage" else "record", fail)
    result = adapter.acquire(request(path))
    assert not result.accepted
    assert result.errors == (f"{stage}_error",)
    assert (result.artifact is None) == (stage == "storage")
    assert (result.event_id is None) == (stage == "provenance")


@pytest.mark.parametrize("field", ["source_id", "logical_key", "locator"])
def test_invalid_attribution_is_not_invented(adapter, tmp_path, field):
    fields = dict(path=tmp_path / "fixture.html", source_id="s", logical_key="k", locator="l")
    fields[field] = " "
    result = adapter.acquire(DocumentRequest(**fields))
    assert result.errors == ("invalid_identity_or_locator",)
    assert result.event_id is None
    assert not list(adapter.artifacts.root.iterdir())


def test_mismatched_stores_are_configuration_error(adapter, tmp_path):
    with pytest.raises(ValueError, match="same ArtifactStore"):
        LocalDocumentAdapter(ArtifactStore(tmp_path / "other"), adapter.provenance)
