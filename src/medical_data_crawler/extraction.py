"""Small common interface for offline extractors and contract-compatible blocks."""

from dataclasses import dataclass, field
from typing import BinaryIO, Literal, Protocol

ExtractionStatus = Literal["success", "partial", "failed"]


def empty_metadata() -> dict:
    return dict(title=None, language=None, authors=None, published_on=None)


@dataclass(frozen=True)
class ContentBlock:
    kind: str
    level: int | None
    text: str

    def to_dict(self) -> dict:
        return dict(kind=self.kind, level=self.level, text=self.text)


@dataclass(frozen=True)
class PageBoundary:
    """One-based source page; zero-based, half-open block range, including empty pages."""

    page_number: int
    block_start: int
    block_end: int
    status: Literal["success", "partial", "no_text", "failed"]


@dataclass(frozen=True)
class ExtractionResult:
    document_type: str
    blocks: tuple[ContentBlock, ...]
    method: str
    version: str
    profile: str
    status: ExtractionStatus
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    metadata: dict = field(default_factory=empty_metadata)
    pages: tuple[PageBoundary, ...] = ()
    page_count: int | None = None
    source_encoding: str | None = None


class Extractor(Protocol):
    def extract(self, data: bytes | BinaryIO) -> ExtractionResult:
        """Read bytes or a borrowed seekable binary stream at document start; never close it."""
        ...


def extraction_result(
    *,
    document_type: str,
    method: str,
    version: str,
    profile: str,
    blocks=(),
    warnings=(),
    errors=(),
    incomplete: bool = False,
    **details,
) -> ExtractionResult:
    blocks, warnings, errors = tuple(blocks), tuple(warnings), tuple(errors)
    if not blocks:
        status: ExtractionStatus = "failed"
        errors = errors or ("no_extractable_text",)
    elif incomplete or errors:
        status = "partial"
        warnings = warnings or ("incomplete_extraction",)
    else:
        status = "success"
    return ExtractionResult(
        document_type, blocks, method, version, profile, status, warnings, errors, **details
    )
