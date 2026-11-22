"""Publish and verify local Structured Raw batches using a manifest as the commit point."""

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

from .contract import validate_record
from .errors import FoundationError, RecordValidationError
from .pipeline import PipelineResult
from .provenance import ProvenanceStore
from .storage import ArtifactStore, StorageError

_EVENT_ID = re.compile(r"[0-9a-f]{32}")
_DOCUMENT_ID = re.compile(r"doc:[0-9a-f]{64}")


class ExportError(FoundationError):
    """A safe error code and, for an individual item, its batch index."""

    def __init__(self, code: str, input_index: int | None = None):
        super().__init__(code)
        self.code = code
        self.input_index = input_index


@dataclass(frozen=True)
class VerificationResult:
    error_code: str | None = None
    input_index: int | None = None

    @property
    def valid(self) -> bool:
        return self.error_code is None


@cache
def _manifest_validator() -> Draft202012Validator:
    resource = files("medical_data_crawler").joinpath("schemas/export-manifest-0.1.json")
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker(formats=["date-time"]))


def _summary(records: list[dict], omissions: list[dict]) -> dict:
    extraction = dict(success=0, partial=0, failed=0)
    for entry in records:
        extraction[entry["extraction_status"]] += 1
    skipped = sum(entry["status"] == "skipped" for entry in omissions)
    return dict(
        total=len(records) + len(omissions),
        exported=len(records),
        skipped=skipped,
        failed=len(omissions) - skipped,
        extraction=extraction,
    )


def _record_path(index: int) -> str:
    return f"records/{index}.json"


def validate_manifest(manifest: object) -> None:
    """Check schema, summary, and that each input is accounted for exactly once."""
    if not _manifest_validator().is_valid(manifest):
        raise ExportError("manifest_invalid")
    records = manifest["records"]
    omissions = manifest["omissions"]
    indices = sorted(entry["input_index"] for entry in records + omissions)
    if (
        indices != list(range(len(indices)))
        or manifest["summary"] != _summary(records, omissions)
        or any(entry["record_path"] != _record_path(int(entry["input_index"])) for entry in records)
        or any(entry["event_id"] and not entry["document_id"] for entry in omissions)
    ):
        raise ExportError("manifest_invalid")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")


def _publish(path: Path, payload: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as out:
            temporary = Path(out.name)
            if out.write(payload) != len(payload):
                raise OSError("short write")
            out.flush()
            os.fsync(out.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink()


def _read_file(path: Path, code: str) -> bytes:
    try:
        # Require the expected path itself, including its parent directories.
        if path.resolve(strict=True) != path or path.is_symlink() or not path.is_file():
            raise ExportError(code)
        return path.read_bytes()
    except (OSError, RuntimeError):
        raise ExportError(code) from None


def _decode(payload: bytes, code: str) -> object:
    try:
        return json.loads(payload.decode("utf-8"))
    except (ValueError, RecursionError):
        raise ExportError(code) from None


def _load_event(provenance: ProvenanceStore, event_id: str | None) -> dict:
    code = "provenance_integrity_error"
    if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id):
        raise ExportError(code)
    try:
        root = provenance.root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ExportError(code) from None
    event = _decode(_read_file(root / f"{event_id}.json", code), code)
    if (
        not isinstance(event, dict)
        or event.get("event_version") != "0.1"
        or event.get("event_id") != event_id
    ):
        raise ExportError(code)
    return event


def _check_references(record: dict, event: dict, artifacts: ArtifactStore) -> None:
    source = record["source"]
    original = record["original"]
    if (
        event.get("status") != "accepted"
        or event.get("error_code") is not None
        or event.get("document_id") != record["document_id"]
        or source["context"] != f"provenance_event:{event['event_id']}"
        or any(event.get(key) != source[key] for key in ("source_id", "locator", "acquired_at"))
        or event.get("artifact_reference") != original["reference"]
        or event.get("sha256") != original["sha256"]
        or event.get("byte_size") != original["byte_length"]
    ):
        raise ExportError("provenance_integrity_error")
    try:
        artifact = artifacts.verify(original["sha256"])
    except StorageError:
        raise ExportError("original_integrity_error") from None
    if artifact.reference != original["reference"] or artifact.byte_size != original["byte_length"]:
        raise ExportError("original_integrity_error")


def _validate_record(record: object) -> None:
    try:
        validate_record(record)
    except RecordValidationError:
        raise ExportError("record_validation_error") from None


def _record_entry(record: dict, event_id: str, index: int, payload: bytes) -> dict:
    return dict(
        input_index=index,
        document_id=record["document_id"],
        event_id=event_id,
        record_path=_record_path(index),
        record_sha256=hashlib.sha256(payload).hexdigest(),
        record_byte_size=len(payload),
        original_reference=record["original"]["reference"],
        original_sha256=record["original"]["sha256"],
        extraction_status=record["extraction"]["status"],
        reuse=record["rights"]["reuse"],
    )


def _export_record(
    result: PipelineResult, index: int, batch: Path, provenance: ProvenanceStore
) -> dict:
    acquired = result.acquisition
    if acquired is None or not acquired.accepted:
        raise ExportError("acquisition_failed")
    if result.record is None:
        if "record_not_built_missing_rights" in result.warnings:
            raise ExportError("missing_access_basis")
        if "artifact_read_error" in result.errors:
            raise ExportError("artifact_read_error")
        raise ExportError("record_validation_error")

    record = result.record
    _validate_record(record)
    try:
        payload = _json_bytes(record)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise ExportError("record_encoding_error") from None
    event = _load_event(provenance, acquired.event_id)
    if (
        record["document_id"] != acquired.document_id
        or not _DOCUMENT_ID.fullmatch(record["document_id"])
        or record["source"]["source_id"] != result.request.source_id
        or record["source"]["locator"] != result.request.locator
        or record["source"]["acquired_at"] != acquired.acquired_at.isoformat()
        or record["original"]["sha256"] != acquired.artifact.sha256
    ):
        raise ExportError("provenance_integrity_error")
    _check_references(record, event, provenance.artifacts)
    entry = _record_entry(record, acquired.event_id, index, payload)
    try:
        _publish(batch / entry["record_path"], payload)
    except OSError:
        raise ExportError("record_write_error") from None
    return entry


def _omission(result: PipelineResult, index: int, code: str, provenance: ProvenanceStore) -> dict:
    identity = event_id = None
    acquired = result.acquisition
    if (
        acquired
        and isinstance(acquired.document_id, str)
        and _DOCUMENT_ID.fullmatch(acquired.document_id)
    ):
        identity = acquired.document_id
        with suppress(ExportError):
            event = _load_event(provenance, acquired.event_id)
            if (
                event.get("document_id") == identity
                and event.get("source_id") == result.request.source_id
                and event.get("locator") == result.request.locator
                and event.get("acquired_at") == acquired.acquired_at.isoformat()
            ):
                event_id = acquired.event_id
    return dict(
        input_index=index,
        document_id=identity,
        event_id=event_id,
        status="skipped" if code == "missing_access_basis" else "failed",
        code=code,
    )


def _verify_entries(manifest: dict, batch: Path, provenance: ProvenanceStore) -> None:
    for entry in manifest["records"]:
        index = int(entry["input_index"])
        try:
            payload = _read_file(batch / _record_path(index), "record_read_error")
            if (
                len(payload) != entry["record_byte_size"]
                or hashlib.sha256(payload).hexdigest() != entry["record_sha256"]
            ):
                raise ExportError("record_integrity_error")
            record = _decode(payload, "record_validation_error")
            _validate_record(record)
            if _record_entry(record, entry["event_id"], index, payload) != entry:
                raise ExportError("manifest_record_mismatch")
            event = _load_event(provenance, entry["event_id"])
            _check_references(record, event, provenance.artifacts)
        except ExportError as error:
            raise ExportError(error.code, index) from None
    for entry in manifest["omissions"]:
        if entry["event_id"] is None:
            continue
        try:
            event = _load_event(provenance, entry["event_id"])
            if event.get("document_id") != entry["document_id"]:
                raise ExportError("provenance_integrity_error")
        except ExportError as error:
            raise ExportError(error.code, entry["input_index"]) from None


def export_batch(
    results: Iterable[PipelineResult], output_root: Path, provenance: ProvenanceStore
) -> Path:
    """Export a fresh batch. Only a batch with a manifest has been published."""
    batch_id = uuid4().hex
    created_at = datetime.now(UTC).isoformat()
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        batch = output_root.resolve(strict=True) / batch_id
        batch.mkdir()
    except (OSError, RuntimeError):
        raise ExportError("batch_create_error") from None
    records: list[dict] = []
    omissions: list[dict] = []
    manifest_path = batch / "manifest.json"
    attempted = 0
    try:
        (batch / "records").mkdir()
        for index, result in enumerate(results):
            attempted = index + 1
            try:
                records.append(_export_record(result, index, batch, provenance))
            except ExportError as error:
                omissions.append(_omission(result, index, error.code, provenance))

        manifest = dict(
            manifest_version="0.1",
            batch_id=batch_id,
            created_at=created_at,
            structured_raw_version="0.1",
            records=records,
            omissions=omissions,
            summary=_summary(records, omissions),
        )
        validate_manifest(manifest)
        _verify_entries(manifest, batch, provenance)
        _publish(manifest_path, _json_bytes(manifest))
        return manifest_path
    except OSError:
        raise ExportError("batch_write_error") from None
    finally:
        # The link itself commits the batch, even if interrupted before _publish returns.
        try:
            manifest_path.lstat()
        except FileNotFoundError:
            for index in range(attempted):
                with suppress(OSError):
                    (batch / _record_path(index)).unlink()
            with suppress(OSError):
                (batch / "records").rmdir()
            with suppress(OSError):
                batch.rmdir()
        except OSError:
            # Preserve files if the filesystem cannot confirm the manifest is absent.
            pass


def verify_batch(manifest_path: Path, provenance: ProvenanceStore) -> VerificationResult:
    """Check a published batch on disk, returning the first issue with a safe code."""
    manifest_path = manifest_path.absolute()
    try:
        manifest = _decode(_read_file(manifest_path, "manifest_read_error"), "manifest_invalid")
        validate_manifest(manifest)
        if (
            manifest_path.name != "manifest.json"
            or manifest_path.parent.name != manifest["batch_id"]
        ):
            raise ExportError("manifest_invalid")
        _verify_entries(manifest, manifest_path.parent, provenance)
    except ExportError as error:
        return VerificationResult(error.code, error.input_index)
    return VerificationResult()
