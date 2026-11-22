import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO

import pytest

from medical_data_crawler.provenance import ProvenanceError, ProvenanceStore, document_id
from medical_data_crawler.storage import ArtifactStore, StorageError


def test_store_and_deduplicate(tmp_path):
    store = ArtifactStore(tmp_path)
    first = store.put(b"abc")
    assert first.sha256 == hashlib.sha256(b"abc").hexdigest()
    assert first.byte_size == 3
    before = (tmp_path / first.reference).stat().st_mtime_ns
    assert store.put(BytesIO(b"abc")) == first
    assert (tmp_path / first.reference).stat().st_mtime_ns == before
    assert store.put(b"xyz") != first
    out = BytesIO()
    assert store.copy_to(first.sha256, out) == first
    assert out.getvalue() == b"abc"
    assert len(list(tmp_path.iterdir())) == 2


def test_corruption_is_preserved(tmp_path):
    store = ArtifactStore(tmp_path)
    artifact = store.put(b"abc")
    path = tmp_path / artifact.reference
    path.write_bytes(b"bad")
    with pytest.raises(StorageError):
        store.put(b"abc")
    with pytest.raises(StorageError):
        store.copy_to(artifact.sha256, BytesIO())
    assert path.read_bytes() == b"bad"
    assert not list(tmp_path.glob(".pending-*"))


@pytest.mark.parametrize("checksum", ["a" * 64, "../unsafe"])
def test_missing_or_invalid_reference(tmp_path, checksum):
    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).verify(checksum)


def test_empty_rejected(tmp_path):
    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).put(b"")
    assert not list(tmp_path.iterdir())


def test_interrupted_read(tmp_path):
    class Interrupted:
        def read(self, size):
            raise OSError("secret")

    with pytest.raises(StorageError, match="Không lưu"):
        ArtifactStore(tmp_path).put(Interrupted())
    assert not list(tmp_path.iterdir())


def test_publish_failure(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("secret")

    monkeypatch.setattr("medical_data_crawler.storage.os.link", fail)
    with pytest.raises(StorageError):
        ArtifactStore(tmp_path).put(b"abc")
    assert not list(tmp_path.iterdir())


def test_large_stream_bounded_reads(tmp_path):
    class Large:
        remaining = 1000

        def read(self, size):
            assert size == 65536
            if self.remaining == 0:
                return b""
            self.remaining -= 1
            return b"x" * size

    store = ArtifactStore(tmp_path)
    artifact = store.put(Large())
    assert artifact.byte_size == 65536000
    assert store.verify(artifact.sha256) == artifact


def test_concurrent_publish(tmp_path):
    store = ArtifactStore(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        artifacts = list(pool.map(store.put, [b"abc"] * 20))
    assert len(set(artifacts)) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_provenance_and_versions(tmp_path):
    artifacts = ArtifactStore(tmp_path / "originals")
    events = ProvenanceStore(tmp_path / "events", artifacts)
    first = artifacts.put(b"abc")
    second = artifacts.put(b"def")
    for source, checksum in [("a", first.sha256), ("b", first.sha256), ("a", second.sha256)]:
        events.record(
            source_id=source,
            logical_key="document-1",
            locator="safe-local-key",
            acquired_at=datetime.now(UTC),
            checksum=checksum,
        )
    records = [json.loads(path.read_text("utf-8")) for path in events.root.glob("*.json")]
    assert len({r["event_id"] for r in records}) == 3
    assert len({r["document_id"] for r in records if r["source_id"] == "a"}) == 1
    assert len({r["sha256"] for r in records}) == 2
    assert document_id("a", "document-1") == document_id("a", "document-1")
    assert document_id("a", "document-1") != document_id("b", "document-1")
    events.record(
        source_id="a",
        logical_key="document-1",
        locator="safe-local-key",
        acquired_at=datetime.now(UTC),
        checksum=None,
        error_code="read_error",
    )
    with pytest.raises(ProvenanceError):
        events.record(
            source_id="a",
            logical_key="document-1",
            locator="safe-local-key",
            acquired_at=datetime.now(UTC),
            checksum="0" * 64,
        )
