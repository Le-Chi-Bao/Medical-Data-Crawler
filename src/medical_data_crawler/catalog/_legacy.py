"""Read one verified Structured Raw v0.1 reference without copying its content."""

import hashlib
import json
import re
from pathlib import Path

from ..export import ExportError, _check_references, _load_event, _read_file, verify_batch
from ..provenance import ProvenanceStore
from ..source_policy import SourcePolicyError, public_document_host
from .model import AccessDomain, CatalogError, encode_json


def read_verified_record(
    manifest_path: Path, provenance: ProvenanceStore, input_index: int, domain: AccessDomain
) -> tuple[dict, str, int]:
    if type(input_index) is not int or not 0 <= input_index <= 2**31 - 1:
        raise CatalogError("invalid_legacy_index")
    if not isinstance(provenance, ProvenanceStore):
        raise CatalogError("legacy_batch_invalid")
    try:
        path = Path(manifest_path).absolute()
        result = verify_batch(path, provenance)
        if not result.valid or result.manifest is None:
            raise CatalogError("legacy_batch_invalid")
    except (OSError, ValueError, TypeError, RuntimeError):
        raise CatalogError("legacy_batch_invalid") from None
    return read_verified_entry(path, provenance, input_index, domain, result.manifest)


def read_verified_entry(
    path: Path,
    provenance: ProvenanceStore,
    input_index: int,
    domain: AccessDomain,
    manifest: dict,
    *,
    max_file_bytes: int | None = None,
) -> tuple[dict, str, int]:
    """Private adapter for a batch already verified by the controlled backfill service."""
    try:
        entry = next(
            (record for record in manifest["records"] if record["input_index"] == input_index), None
        )
        if entry is None:
            raise CatalogError("legacy_entry_not_found")
        event = _load_event(provenance, entry["event_id"], max_file_bytes)

        # Hash the exact bytes read here, since the verifier completed before this read.
        record_path = path.parent / entry["record_path"]
        if max_file_bytes is not None and entry["record_byte_size"] > max_file_bytes:
            raise CatalogError("verification_size_limit")
        payload = _read_file(record_path, "record_read_error", entry["record_byte_size"])
        if (
            len(payload) != entry["record_byte_size"]
            or hashlib.sha256(payload).hexdigest() != entry["record_sha256"]
        ):
            raise CatalogError("legacy_batch_invalid")
        record = json.loads(payload)
        _check_references(record, event, provenance.artifacts)
    except (
        ExportError,
        OSError,
        ValueError,
        TypeError,
        OverflowError,
        RecursionError,
        RuntimeError,
    ):
        raise CatalogError("legacy_batch_invalid") from None

    source = record["source"]
    locator, source_id = source["locator"], source["source_id"]
    if domain.visibility == "public":
        if source_id.startswith("internal-") or "internal" in event:
            raise CatalogError("legacy_binding_mismatch")
        try:
            public_document_host(locator)
        except SourcePolicyError:
            raise CatalogError("legacy_binding_mismatch") from None
    elif (
        not source_id.startswith("internal-")
        or not re.fullmatch(r"internal:[a-z][a-z0-9._-]{0,63}", locator)
        or not isinstance(event.get("internal"), dict)
    ):
        raise CatalogError("legacy_binding_mismatch")

    batch_id, event_id, record_sha256 = (
        manifest["batch_id"],
        entry["event_id"],
        entry["record_sha256"],
    )
    key = hashlib.sha256(encode_json([batch_id, event_id, record_sha256]).encode("utf-8"))
    return (
        {
            "id": f"legacy-{key.hexdigest()}",
            "legacy_document_id": record["document_id"],
            "source_id": source_id,
            "locator": locator,
            "acquired_at": source["acquired_at"],
            "batch_id": batch_id,
            "event_id": event_id,
            "record_sha256": record_sha256,
            "original_sha256": entry["original_sha256"],
        },
        record["original"]["media_type"],
        record["original"]["byte_length"],
    )
