"""Offline acquisition; callers own source identity and sanitized locators."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .provenance import ProvenanceError, ProvenanceStore, document_id
from .storage import Artifact, ArtifactStore, StorageError


@dataclass(frozen=True)
class DocumentRequest:
    # Non-filesystem adapters may use locator with path=None in a later session.
    path: Path | None
    source_id: str
    logical_key: str
    locator: str


@dataclass(frozen=True)
class AcquisitionResult:
    request: DocumentRequest
    document_id: str | None
    acquired_at: datetime
    media_type: str | None
    artifact: Artifact | None
    event_id: str | None
    errors: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return self.artifact is not None and self.event_id is not None and not self.errors


class AcquisitionAdapter(Protocol):
    def acquire(self, request: DocumentRequest) -> AcquisitionResult: ...


class LocalDocumentAdapter:
    """Accept explicit local paths only; never enumerate or fetch sources."""

    def __init__(self, artifacts: ArtifactStore, provenance: ProvenanceStore):
        if provenance.artifacts is not artifacts:
            raise ValueError("Acquisition and provenance must use the same ArtifactStore")
        self.artifacts = artifacts
        self.provenance = provenance

    def acquire(self, request: DocumentRequest) -> AcquisitionResult:
        acquired_at = datetime.now(UTC)
        identity = None
        artifact = None
        event_id = None
        media_type = None
        errors: list[str] = []
        try:
            identity = document_id(request.source_id, request.logical_key)
            if not isinstance(request.locator, str) or not request.locator.strip():
                raise ProvenanceError("Invalid locator")
            request.locator.encode("utf-8")
        except (ProvenanceError, UnicodeError):
            # An event cannot be validly attributed with invalid identity/locator.
            errors.append("invalid_identity_or_locator")
        else:
            try:
                path = Path(request.path)
                media_type = {
                    ".html": "text/html",
                    ".htm": "text/html",
                    ".pdf": "application/pdf",
                }.get(path.suffix.lower())
                if media_type is None:
                    errors.append("unsupported_format")
                else:
                    data = path.read_bytes()
                    if not data:
                        errors.append("empty_file")
                    else:
                        artifact = self.artifacts.put(data)
            except FileNotFoundError:
                errors.append("file_not_found")
            except OSError:
                errors.append("read_error")
            except (TypeError, ValueError):
                errors.append("invalid_input")
            except StorageError:
                errors.append("storage_error")
            try:
                # The existing event vocabulary is deliberately unchanged.
                failure = None
                if artifact is None:
                    failure = (
                        "invalid_input"
                        if errors[0] in {"unsupported_format", "empty_file", "invalid_input"}
                        else "read_error"
                    )
                event_id = self.provenance.record(
                    source_id=request.source_id,
                    logical_key=request.logical_key,
                    locator=request.locator,
                    acquired_at=acquired_at,
                    checksum=artifact.sha256 if artifact else None,
                    error_code=failure,
                )
            except ProvenanceError:
                errors.append("provenance_error")
        return AcquisitionResult(
            request, identity, acquired_at, media_type, artifact, event_id, tuple(errors)
        )
