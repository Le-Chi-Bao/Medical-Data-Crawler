"""Offline orchestration and optional in-memory v0.1 records; no batch exporter."""

from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from .acquisition import AcquisitionAdapter, AcquisitionResult, DocumentRequest
from .contract import validate_record
from .errors import RecordValidationError
from .extraction import ExtractionResult, Extractor, extraction_result
from .html_extraction import HTMLExtractor
from .pdf_extraction import PDFExtractor
from .storage import ArtifactStore, StorageError


@dataclass(frozen=True)
class RecordRights:
    """Caller-supplied evidence; a local path is not evidence of redistribution rights."""

    access_basis: str
    reuse: Literal["unknown", "permitted", "restricted"] = "unknown"
    evidence: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    request: DocumentRequest
    acquisition: AcquisitionResult | None
    extraction: ExtractionResult | None
    record: dict | None
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


def detect_media_type(data: bytes, hint: str | None) -> str:
    """PDF signature wins; HTML tolerates fragments/plain text with an HTML suffix.

    A PDF suffix retains PDF routing for damaged-header failure reporting.
    Known binary signatures and unexplained NUL bytes are never treated as HTML.
    This is limited format detection, not a complete file-type classifier.
    """
    if data.lstrip(b" \t\r\n").startswith(b"%PDF-") or hint == "application/pdf":
        return "application/pdf"
    binary = data.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"PK\x03\x04"))
    unicode_bom = data.startswith((b"\xff\xfe", b"\xfe\xff", b"\x00\x00\xfe\xff"))
    if hint == "text/html" and not binary and (b"\x00" not in data or unicode_bom):
        return "text/html"
    return "application/octet-stream"


class OfflinePipeline:
    def __init__(self, artifacts: ArtifactStore, acquisition: AcquisitionAdapter):
        self.artifacts = artifacts
        self.acquisition = acquisition
        self.extractors: dict[str, Extractor] = {
            "text/html": HTMLExtractor(),
            "application/pdf": PDFExtractor(),
        }

    def process(
        self, request: DocumentRequest, *, rights: RecordRights | None = None
    ) -> PipelineResult:
        try:
            acquired = self.acquisition.acquire(request)
        except Exception:
            return PipelineResult(request, None, None, None, (), ("acquisition_unexpected_error",))
        if not acquired.accepted:
            return PipelineResult(request, acquired, None, None, (), acquired.errors)
        try:
            stream = BytesIO()
            # Extraction sees only verified immutable storage, never the source path.
            self.artifacts.copy_to(acquired.artifact.sha256, stream)
            data = stream.getvalue()
        except StorageError:
            return PipelineResult(request, acquired, None, None, (), ("artifact_read_error",))
        media_type = detect_media_type(data, acquired.media_type)
        extractor = self.extractors.get(media_type)
        if extractor is None:
            extracted = extraction_result(
                document_type="unknown",
                method="offline-format-detection",
                version="1.0",
                profile="offline-dispatch-v1",
                errors=("unsupported_content_format",),
            )
        else:
            try:
                extracted = extractor.extract(data)
            except Exception:
                extracted = extraction_result(
                    document_type="pdf" if media_type == "application/pdf" else "html",
                    method="offline-pipeline/dispatch",
                    version="1.0",
                    profile="offline-dispatch-v1",
                    errors=("extractor_unexpected_error",),
                )
        warnings = list(extracted.warnings)
        errors = list(extracted.errors)
        if media_type != acquired.media_type:
            warnings.append("format_extension_mismatch")
        record = None
        if rights is None:
            warnings.append("record_not_built_missing_rights")
        else:
            if extracted.pages:
                warnings.append("v0.1_page_boundaries_internal_only")
            record = self._record(acquired, extracted, media_type, rights, warnings)
            try:
                validate_record(record)
            except RecordValidationError:
                errors.append("record_validation_error")
                record = None
        return PipelineResult(request, acquired, extracted, record, tuple(warnings), tuple(errors))

    def process_many(self, requests, *, rights: RecordRights | None = None) -> list[PipelineResult]:
        """Process only explicitly supplied inputs, sequentially; no source discovery."""
        return [self.process(request, rights=rights) for request in requests]

    @staticmethod
    def _record(acquired, extracted, media_type, rights, warnings) -> dict:
        artifact = acquired.artifact
        return {
            "schema_version": "0.1",
            "document_id": acquired.document_id,
            "source": {
                "source_id": acquired.request.source_id,
                "locator": acquired.request.locator,
                "acquired_at": acquired.acquired_at.isoformat(),
                "context": f"provenance_event:{acquired.event_id}",
            },
            "original": {
                "reference": artifact.reference,
                "media_type": media_type,
                "byte_length": artifact.byte_size,
                "sha256": artifact.sha256,
            },
            "content": [block.to_dict() for block in extracted.blocks],
            "metadata": dict(extracted.metadata),
            "scope": "unknown",
            "scope_evidence": None,
            "audience": "unknown",
            "audience_evidence": None,
            "extraction": {
                "status": extracted.status,
                "method": extracted.method,
                "version": extracted.version,
                "configuration": {"profile": extracted.profile},
                "warnings": list(warnings),
                "errors": list(extracted.errors),
            },
            "rights": {
                "access_basis": rights.access_basis,
                "reuse": rights.reuse,
                "evidence": rights.evidence,
            },
        }
