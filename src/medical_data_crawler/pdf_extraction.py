"""Text-layer PDF extraction; page order is known, visual reading order is not."""

import re
from io import BytesIO

import pypdf
from pypdf import PdfReader

from .extraction import (
    ContentBlock,
    ExtractionResult,
    PageBoundary,
    empty_metadata,
    extraction_result,
)


class PDFExtractor:
    profile = "pdf-plain-v1"
    version = f"1.0/pypdf-{pypdf.__version__}"

    def extract(self, data: bytes) -> ExtractionResult:
        blocks: list[ContentBlock] = []
        boundaries: list[PageBoundary] = []
        warnings = ["pdf_layout_unverified"]
        errors: list[str] = []
        metadata = empty_metadata()
        page_count = None
        incomplete = False
        try:
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                errors.append("pdf_encrypted")
            else:
                page_count = len(reader.pages)
                try:
                    info = reader.metadata or {}
                    for source, target in [("/Title", "title"), ("/Author", "authors")]:
                        value = info.get(source)
                        if isinstance(value, str) and value.strip():
                            metadata[target] = (
                                [value.strip()] if target == "authors" else value.strip()
                            )
                    language = reader.root_object.get("/Lang")
                    if isinstance(language, str) and language.strip():
                        metadata["language"] = language.strip()
                except Exception:
                    warnings.append("pdf_metadata_error")
                for index in range(page_count):
                    number = index + 1
                    start = len(blocks)
                    positions: list[tuple[float, float]] = []

                    def inspect_fragment(text, cm, tm, font, font_size, positions=positions):
                        if text.strip():
                            # Transform text origin into page coordinates. This is a
                            # conservative layout hint, not a reading-order solver.
                            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                            positions.append((float(x), float(y)))

                    try:
                        text = reader.pages[index].extract_text(
                            extraction_mode="plain",
                            orientations=(0, 90, 180, 270),
                            visitor_text=inspect_fragment,
                        )
                        text = text.replace("\r\n", "\n").replace("\r", "\n")
                        page_blocks = [
                            ContentBlock("paragraph", None, paragraph.strip())
                            for paragraph in re.split(r"\n[ \t]*\n+", text)
                            if paragraph.strip()
                        ]
                        complex_layout = self._complex_layout(positions)
                        if not page_blocks:
                            status = "no_text"
                            warnings.append(f"pdf_page_{number}_no_text")
                            incomplete = True
                        elif complex_layout:
                            status = "partial"
                            warnings.append(f"pdf_page_{number}_complex_layout")
                            incomplete = True
                        else:
                            status = "success"
                        blocks.extend(page_blocks)
                    except Exception:
                        status = "failed"
                        incomplete = True
                        errors.append(f"pdf_page_{number}_error")
                        warnings.append(f"pdf_page_{number}_incomplete")
                    boundaries.append(PageBoundary(number, start, len(blocks), status))
        except Exception:
            errors.append("pdf_read_error")
        return extraction_result(
            document_type="pdf",
            method="pypdf/plain",
            version=self.version,
            profile=self.profile,
            blocks=blocks,
            warnings=warnings,
            errors=errors,
            incomplete=incomplete,
            metadata=metadata,
            pages=tuple(boundaries),
            page_count=page_count,
        )

    @staticmethod
    def _complex_layout(positions: list[tuple[float, float]]) -> bool:
        # Widely separated text origins on one line can indicate columns or a table.
        # Sorted adjacent rows avoid quadratic comparisons on text-heavy pages.
        by_y = sorted(positions, key=lambda position: position[1])
        row_min = row_max = 0.0
        row_y = None
        for x, y in by_y:
            if row_y is None or y - row_y > 2:
                row_min = row_max = x
                row_y = y
            else:
                row_min, row_max = min(row_min, x), max(row_max, x)
                if row_max - row_min >= 72:
                    return True
        return False
