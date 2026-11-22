from datetime import UTC, datetime, tzinfo
from io import BytesIO, StringIO
from pathlib import Path

import pytest

from medical_data_crawler.provenance import ProvenanceError, ProvenanceStore, document_id
from medical_data_crawler.storage import ArtifactStore, StorageError


@pytest.mark.parametrize("value", [None, 1, [], {}, "", " ", "\ud800"])
@pytest.mark.parametrize("field", ["source_id", "logical_key"])
def test_invalid_identity(value, field):
    fields = dict(source_id="safe", logical_key="key")
    fields[field] = value
    with pytest.raises(ProvenanceError):
        document_id(**fields)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("locator", None),
        ("locator", []),
        ("locator", "\ud800"),
        ("source_id", None),
        ("logical_key", ""),
        ("acquired_at", "2026-11-23"),
        ("acquired_at", datetime(2026, 11, 23)),
        ("checksum", []),
        ("checksum", "wrong"),
        ("error_code", []),
    ],
)
def test_record_invalid_input_leaves_no_event(tmp_path, field, value):
    store = ArtifactStore(tmp_path / "artifacts")
    events = ProvenanceStore(tmp_path / "events", store)
    args = dict(
        source_id="safe",
        logical_key="key",
        locator="safe",
        acquired_at=datetime.now(UTC),
        checksum=None,
        error_code="read_error",
    )
    args[field] = value
    with pytest.raises(ProvenanceError):
        events.record(**args)
    assert not list(events.root.iterdir())


def test_invalid_timezone(tmp_path):
    class BadTimezone(tzinfo):
        def utcoffset(self, dt):
            raise ValueError("secret")

    events = ProvenanceStore(tmp_path / "events", ArtifactStore(tmp_path / "artifacts"))
    with pytest.raises(ProvenanceError):
        events.record(
            source_id="safe",
            logical_key="key",
            locator="safe",
            checksum=None,
            error_code="read_error",
            acquired_at=datetime(2026, 11, 23, tzinfo=BadTimezone()),
        )


@pytest.mark.parametrize("source", [None, object(), StringIO("abc")])
def test_invalid_stream_cleanup(tmp_path, source):
    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).put(source)
    assert not list(tmp_path.iterdir())


def test_failure_after_first_chunk(tmp_path):
    class Interrupted:
        calls = 0

        def read(self, size):
            self.calls += 1
            if self.calls == 1:
                return b"abc"
            raise OSError("secret")

    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).put(Interrupted())
    assert not list(tmp_path.iterdir())


def test_closed_stream(tmp_path):
    stream = BytesIO(b"abc")
    stream.close()
    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).put(stream)
    assert not list(tmp_path.iterdir())


def test_fsync_failure_cleanup(tmp_path, monkeypatch):
    def fail(fd):
        raise OSError("secret")

    monkeypatch.setattr("medical_data_crawler.storage.os.fsync", fail)
    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).put(b"abc")
    assert not list(tmp_path.iterdir())


def test_cleanup_does_not_mask_primary_error(tmp_path, monkeypatch):
    def fail_unlink(*args, **kwargs):
        raise OSError("secret")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(StorageError, match="rỗng") as error:
        ArtifactStore(tmp_path).put(b"")
    assert error.value.__notes__ == ["Không dọn được temporary file của artifact"]


def test_cleanup_after_publish_reports_domain_error(tmp_path, monkeypatch):
    def fail_unlink(*args, **kwargs):
        raise OSError("secret")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    store = ArtifactStore(tmp_path)
    with pytest.raises(StorageError, match="đã công bố"):
        store.put(b"abc")
    assert store.verify("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


def test_short_destination_write(tmp_path):
    class ShortWriter:
        def write(self, data):
            return 0

    store = ArtifactStore(tmp_path)
    artifact = store.put(b"abc")
    with pytest.raises(StorageError, match="đủ byte"):
        store.copy_to(artifact.sha256, ShortWriter())


def test_short_temporary_write(tmp_path, monkeypatch):
    import tempfile

    original = tempfile.NamedTemporaryFile

    class ShortFile:
        def __init__(self, *args, **kwargs):
            self.file = original(*args, **kwargs)
            self.name = self.file.name

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def write(self, data):
            self.file.write(data[:1])
            return 1

    monkeypatch.setattr("medical_data_crawler.storage.tempfile.NamedTemporaryFile", ShortFile)
    with pytest.raises(StorageError, match="đủ byte"):
        ArtifactStore(tmp_path).put(b"abc")
    assert not list(tmp_path.iterdir())


def test_provenance_publish_failure_cleanup(tmp_path, monkeypatch):
    events = ProvenanceStore(tmp_path / "events", ArtifactStore(tmp_path / "artifacts"))

    def fail(*args):
        raise OSError("secret")

    monkeypatch.setattr("medical_data_crawler.provenance.os.link", fail)
    with pytest.raises(ProvenanceError, match="Không công bố"):
        events.record(
            source_id="safe",
            logical_key="key",
            locator="safe",
            checksum=None,
            error_code="read_error",
            acquired_at=datetime.now(UTC),
        )
    assert not list(events.root.iterdir())


def test_invalid_checksum_type(tmp_path):
    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).verify(None)


def test_valid_identity_is_unchanged():
    import hashlib
    import json

    expected = hashlib.sha256(
        json.dumps(["nguồn", "khóa"], ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert document_id("nguồn", "khóa") == "doc:" + expected
