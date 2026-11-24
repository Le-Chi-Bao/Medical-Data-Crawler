"""Controlled offline intake for explicitly approved internal documents."""

import re
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import cached_property
from itertools import chain
from pathlib import Path
from types import MappingProxyType

from ._intake_files import (
    INTAKE_MEDIA_TYPES,
    MAX_INPUT_BYTES,
    IntakeFileError,
    check_local_path,
    private_pdf_diagnostics,
    snapshot_document,
)
from .acquisition import DocumentRequest, LocalDocumentAdapter
from .errors import FoundationError
from .export import ExportError, VerificationResult, export_batch, verify_batch
from .pipeline import OfflinePipeline, PipelineResult, RecordRights
from .provenance import InternalIntakeTrace, ProvenanceStore, document_id
from .storage import ArtifactStore

_SLUG = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*")
_CHECKSUM = re.compile(r"[0-9a-f]{64}")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)
_MAX_ENTRIES = 1000
_OPERATION = "internal_import"


class IntakeError(FoundationError):
    """An intake error carrying only a stable, non-sensitive code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _Binding:
    source_id: str
    logical_key: str
    locator: str
    local_path: str
    format: str
    provider_ref: str
    access_basis: str


@dataclass(frozen=True)
class _Declaration:
    binding: _Binding
    authorization_ref: str
    allow_store: bool
    allow_extract: bool
    expected_sha256: str | None
    reuse: str


@dataclass(frozen=True)
class _Authorization:
    declaration: _Declaration
    active: bool
    expires_at: datetime
    operation: str
    allow_read: bool


_REQUIRED = {
    "source_id",
    "logical_key",
    "locator",
    "local_path",
    "format",
    "provider_ref",
    "access_basis",
    "authorization_ref",
    "allow_store",
    "allow_extract",
}
_OPTIONAL = {"expected_sha256", "reuse"}
_GRANT_FIELDS = {"active", "expires_at", "operation", "allow_read"}


def _slug(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 64 and _SLUG.fullmatch(value) is not None


def _token(value: object, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix) and _slug(value[len(prefix) :])


def _path_text(value: object) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 4096 or not value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return all(ord(char) >= 32 and ord(char) != 127 for char in value)


def _entries(value: object, version_key: str, entries_key: str, code: str) -> list:
    if (
        not isinstance(value, dict)
        or value.keys() != {version_key, entries_key}
        or value[version_key] != "0.1"
        or not isinstance(value[entries_key], list)
        or len(value[entries_key]) > _MAX_ENTRIES
    ):
        raise IntakeError(code)
    return value[entries_key]


def _declaration(value: object, code: str, *, grant: bool = False) -> _Declaration:
    required = _REQUIRED | _GRANT_FIELDS if grant else _REQUIRED
    if not isinstance(value, dict) or not required <= value.keys() <= required | _OPTIONAL:
        raise IntakeError(code)
    if (
        not _token(value["source_id"], "internal-")
        or len(value["source_id"]) > 64
        or not _token(value["locator"], "internal:")
        or any(
            not _slug(value[name])
            for name in ("logical_key", "provider_ref", "authorization_ref", "access_basis")
        )
        or not _path_text(value["local_path"])
        or not isinstance(value["format"], str)
        or value["format"] not in INTAKE_MEDIA_TYPES
        or type(value["allow_store"]) is not bool
        or type(value["allow_extract"]) is not bool
    ):
        raise IntakeError(code)
    checksum = value.get("expected_sha256")
    if "expected_sha256" in value and (
        not isinstance(checksum, str) or _CHECKSUM.fullmatch(checksum) is None
    ):
        raise IntakeError(code)
    reuse = value.get("reuse", "unknown")
    if reuse not in ("unknown", "restricted", "permitted"):
        raise IntakeError(code)
    binding = _Binding(
        value["source_id"],
        value["logical_key"],
        value["locator"],
        value["local_path"],
        value["format"],
        value["provider_ref"],
        value["access_basis"],
    )
    return _Declaration(
        binding,
        value["authorization_ref"],
        value["allow_store"],
        value["allow_extract"],
        checksum,
        reuse,
    )


def parse_authorizations(value: object) -> Mapping[str, _Authorization]:
    """Validate the separate authorization configuration supplied by a trusted caller."""
    code = "invalid_authorization_config"
    approvals = {}
    for entry in _entries(value, "authorization_version", "authorizations", code):
        declaration = _declaration(entry, code, grant=True)
        reference = declaration.authorization_ref
        expires_at = entry["expires_at"]
        operation = entry["operation"]
        if (
            reference in approvals
            or type(entry["active"]) is not bool
            or type(entry["allow_read"]) is not bool
            or not _slug(operation)
            or not isinstance(expires_at, str)
            or _TIMESTAMP.fullmatch(expires_at) is None
        ):
            raise IntakeError(code)
        try:
            expiry = datetime.fromisoformat(expires_at)
        except ValueError:
            raise IntakeError(code) from None
        approvals[reference] = _Authorization(
            declaration, entry["active"], expiry, operation, entry["allow_read"]
        )
    return MappingProxyType(approvals)


@dataclass
class _Item:
    input_index: int
    status: str = "failed"
    code: str | None = None
    document_id: str | None = None
    event_id: str | None = None
    sha256: str | None = None
    export_input_index: int | None = None
    extraction_status: str | None = None


@dataclass(frozen=True)
class IntakeBatchResult:
    report: dict
    manifest_path: Path | None
    verification: VerificationResult | None


class InternalIntakeGateway:
    """Application entrypoint for internal import and validation-only batches."""

    def __init__(
        self,
        *,
        approved_roots: tuple[Path, ...],
        state_root: Path,
        authorizations: Mapping[str, _Authorization],
        max_bytes: int = MAX_INPUT_BYTES,
    ):
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_INPUT_BYTES:
            raise IntakeError("invalid_size_limit")
        try:
            roots = tuple(check_local_path(path) for path in approved_roots)
            if not roots or not all(root.is_dir() for root in roots):
                raise IntakeError("invalid_intake_roots")
        except (IntakeFileError, OSError, TypeError):
            raise IntakeError("invalid_intake_roots") from None
        try:
            self._state_root = check_local_path(state_root)
        except (IntakeFileError, OSError, TypeError):
            raise IntakeError("invalid_state_root") from None
        self._approved_roots = roots
        self._max_bytes = max_bytes
        self._authorizations = dict(authorizations)

    @cached_property
    def _adapter(self) -> LocalDocumentAdapter:
        try:
            original_root = check_local_path(self._state_root / "originals")
            event_root = check_local_path(self._state_root / "provenance")
            artifacts = ArtifactStore(original_root)
            return LocalDocumentAdapter(artifacts, ProvenanceStore(event_root, artifacts))
        except (IntakeFileError, OSError):
            raise IntakeError("storage_unavailable") from None

    def _authorize(self, declaration: _Declaration) -> _Authorization:
        grant = self._authorizations.get(declaration.authorization_ref)
        if not isinstance(grant, _Authorization):
            raise IntakeError("authorization_missing")
        if not grant.active:
            raise IntakeError("authorization_inactive")
        if datetime.now(UTC) >= grant.expires_at:
            raise IntakeError("authorization_expired")
        if grant.operation != _OPERATION:
            raise IntakeError("authorization_operation_mismatch")
        approved = grant.declaration
        if approved.binding != declaration.binding or (
            approved.expected_sha256
            and declaration.expected_sha256
            and approved.expected_sha256 != declaration.expected_sha256
        ):
            raise IntakeError("authorization_binding_mismatch")
        if not grant.allow_read:
            raise IntakeError("read_not_authorized")
        if not (approved.allow_store and declaration.allow_store):
            raise IntakeError("storage_not_authorized")
        if declaration.reuse != "unknown" and declaration.reuse != approved.reuse:
            raise IntakeError("reuse_not_authorized")
        return grant

    def _process(self, value: object, item: _Item, dry_run: bool) -> PipelineResult | None:
        declaration = _declaration(value, "invalid_document_spec")
        grant = self._authorize(declaration)
        binding = grant.declaration.binding
        item.document_id = document_id(binding.source_id, binding.logical_key)
        expected = grant.declaration.expected_sha256 or declaration.expected_sha256
        allow_extract = grant.declaration.allow_extract and declaration.allow_extract
        with snapshot_document(
            binding.local_path,
            self._approved_roots,
            binding.format,
            self._max_bytes,
            expected,
            dry_run=dry_run,
        ) as (stream, checksum):
            if datetime.now(UTC) >= grant.expires_at:
                raise IntakeError("authorization_expired")
            if dry_run:
                item.status = "validated"
                item.sha256 = checksum
                if not allow_extract:
                    item.code = "extraction_not_authorized"
                return None
            adapter = self._adapter
            if datetime.now(UTC) >= grant.expires_at:
                raise IntakeError("authorization_expired")
            request = DocumentRequest(None, binding.source_id, binding.logical_key, binding.locator)
            trace = InternalIntakeTrace(
                provider_ref=binding.provider_ref,
                authorization_ref=declaration.authorization_ref,
                operation=grant.operation,
                format=binding.format,
                expires_at=grant.expires_at.isoformat(),
                allow_read=True,
                allow_store=True,
                allow_extract=allow_extract,
                access_basis=binding.access_basis,
                reuse=declaration.reuse,
            )
            acquired = adapter.acquire_snapshot(
                request,
                stream=stream,
                media_type=INTAKE_MEDIA_TYPES[binding.format],
                expected_sha256=checksum,
                trace=trace,
            )
            if acquired.artifact is not None:
                item.sha256 = acquired.artifact.sha256
            item.event_id = acquired.event_id
            if not acquired.accepted:
                raise IntakeError(acquired.errors[0])
        if not allow_extract:
            item.status, item.code = "stored_only", "extraction_not_authorized"
            return None
        if datetime.now(UTC) >= grant.expires_at:
            raise IntakeError("authorization_expired")
        rights = RecordRights(
            binding.access_basis, declaration.reuse, f"intake:{declaration.authorization_ref}"
        )
        with private_pdf_diagnostics():
            pipeline = OfflinePipeline(adapter.artifacts, adapter)
            result = pipeline.process_acquired(
                acquired, rights=rights, snapshot_dir=adapter.artifacts.root
            )
        if datetime.now(UTC) >= grant.expires_at:
            raise IntakeError("authorization_expired")
        if result.record is None:
            raise IntakeError(
                "artifact_read_error"
                if "artifact_read_error" in result.errors
                else "record_validation_error"
            )
        item.extraction_status = result.record["extraction"]["status"]
        item.code = "extraction_failed" if item.extraction_status == "failed" else None
        return result

    def run(self, spec: object, *, dry_run: bool = False) -> IntakeBatchResult:
        """Process declarations in input order and account for each in a sanitized report."""
        documents = _entries(spec, "intake_version", "documents", "invalid_intake_spec")
        items: list[_Item] = []
        candidates: list[_Item] = []

        def process_documents() -> Iterator[PipelineResult]:
            for index, document in enumerate(documents):
                item = _Item(index)
                items.append(item)
                try:
                    result = self._process(document, item, dry_run)
                except (IntakeError, IntakeFileError) as error:
                    item.status, item.code = "failed", error.code
                except Exception:
                    item.status, item.code = "failed", "intake_unexpected_error"
                else:
                    if result is not None:
                        candidates.append(item)
                        yield result

        manifest = verification = export = batch_error = None
        results = process_documents()
        first = next(results, None)
        if first is not None:
            try:
                output = check_local_path(self._state_root / "exports")
                provenance = self._adapter.provenance
                manifest = export_batch(chain((first,), results), output, provenance)
                verification = verify_batch(manifest, provenance)
                if not verification.valid:
                    raise IntakeError(verification.error_code)
                export = {"batch_id": manifest.parent.name, "verification": "pass"}
                for entry in verification.manifest["records"]:
                    index = entry["input_index"]
                    item = candidates[index]
                    item.export_input_index = index
                    if item.extraction_status != "failed":
                        item.status = "exported"
                for entry in verification.manifest["omissions"]:
                    index = entry["input_index"]
                    item = candidates[index]
                    item.export_input_index = index
                    item.code = entry["code"]
            except (ExportError, IntakeError, IntakeFileError) as error:
                batch_error = error.code
                if manifest is not None:
                    export = {"batch_id": manifest.parent.name, "verification": "failed"}
                # A batch publication failure does not cancel independently approved intake.
                for _ in results:
                    pass
                for item in candidates:
                    item.status, item.code = "failed", batch_error
        summary = dict(total=len(items), failed=0, stored_only=0, exported=0, validated=0)
        for item in items:
            summary[item.status] += 1
        report = dict(
            intake_report_version="0.1",
            dry_run=dry_run,
            summary=summary,
            items=[asdict(item) for item in items],
            export=export,
            batch_error=batch_error,
        )
        return IntakeBatchResult(report, manifest, verification)
