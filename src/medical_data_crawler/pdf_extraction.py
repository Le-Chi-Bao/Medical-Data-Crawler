"""Text-layer PDF extraction; page order is known, visual reading order is not."""

import re
from io import BytesIO
from math import isfinite
from typing import BinaryIO

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
    profile = "pdf-plain-v2"
    version = f"1.1/pypdf-{pypdf.__version__}"

    def extract(self, data: bytes | BinaryIO) -> ExtractionResult:
        blocks: list[ContentBlock] = []
        boundaries: list[PageBoundary] = []
        warnings = ["pdf_layout_unverified"]
        errors: list[str] = []
        metadata = empty_metadata()
        page_count = None
        incomplete = False
        try:
            stream = BytesIO(data) if isinstance(data, bytes) else data
            reader = PdfReader(stream, strict=True)
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
                    positions: list[tuple[float, float, float | None]] = []
                    font_metrics = {}

                    def inspect_fragment(
                        text,
                        cm,
                        tm,
                        font,
                        font_size,
                        positions=positions,
                        font_metrics=font_metrics,
                    ):
                        if text.strip():
                            # Transform text origin into page coordinates. This is a
                            # conservative layout hint, not a reading-order solver.
                            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                            width = self._fragment_width(
                                text, cm, tm, font, font_size, font_metrics
                            )
                            positions.append((float(x), float(y), width))

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
                        if any(width is None for _, _, width in positions):
                            if "pdf_layout_metrics_unavailable" not in warnings:
                                warnings.append("pdf_layout_metrics_unavailable")
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
    def _fragment_width(text, cm, tm, font, font_size, cache) -> float | None:
        try:
            # Use pypdf 7's own font/encoding model rather than inventing glyph
            # widths. This private API is optional: failures retain text and fall
            # back to origin-only detection with an explicit warning.
            from pypdf.generic._font import Font

            scale_x = tm[0] * cm[0] + tm[1] * cm[2]
            scale_y = tm[0] * cm[1] + tm[1] * cm[3]
            if font is None or scale_x <= 0 or abs(scale_y) > 1e-6 or font_size <= 0:
                return None
            key = id(font)
            if key not in cache:
                cache[key] = Font.from_font_resource(font)
            model = cache[key]
            if not model.interpretable:
                return None
            width = max(model.get_text_width(line) for line in text.splitlines())
            width *= font_size * scale_x / 1000
            return float(width) if isfinite(width) and width >= 0 else None
        except Exception:
            return None

    @staticmethod
    def _complex_layout(positions: list[tuple[float, float, float | None]]) -> bool:
        # Merge horizontal text extents before measuring gaps. Far-apart origins
        # alone do not imply columns: long adjacent runs may be a normal line.
        def has_gap(row):
            if not row:
                return False
            intervals = sorted(row)
            right = intervals[0][1]
            for left, end in intervals[1:]:
                if left - right >= 72:
                    return True
                right = max(right, end)
            return False

        by_y = sorted(positions, key=lambda position: position[1])
        row = []
        row_y = None
        for x, y, width in by_y:
            if row_y is None or y - row_y > 2:
                if has_gap(row):
                    return True
                row = []
                row_y = y
            row.append((x, x + (width if width is not None else 0)))
        return has_gap(row)
