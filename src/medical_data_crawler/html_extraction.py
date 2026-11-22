"""DOM order extraction without rendering, network access, or medical rewriting."""

import re

import bs4
from bs4 import BeautifulSoup, Comment, Declaration, Doctype, NavigableString, Tag

from .extraction import ContentBlock, ExtractionResult, empty_metadata, extraction_result

_HEADINGS = {f"h{level}" for level in range(1, 7)}
_BOUNDARIES = _HEADINGS | {
    "p",
    "li",
    "ul",
    "ol",
    "div",
    "section",
    "article",
    "main",
    "header",
    "footer",
    "blockquote",
    "pre",
    "dl",
    "dt",
    "dd",
    "figure",
    "figcaption",
    "address",
    "hr",
    "html",
    "body",
    "table",
}


def _visible_string(node) -> bool:
    return isinstance(node, NavigableString) and not isinstance(
        node, (Comment, Declaration, Doctype)
    )


def _flow_text(tag: Tag) -> str:
    parts = []
    for node in tag.descendants:
        if _visible_string(node):
            parts.append(re.sub(r"\s+", " ", str(node)))
        elif isinstance(node, Tag) and node.name == "br":
            parts.append("\n")
    return "".join(parts).strip()


class HTMLExtractor:
    profile = "html-dom-v1"
    version = f"1.0/beautifulsoup4-{bs4.__version__}/html.parser"

    def extract(self, data: bytes) -> ExtractionResult:
        if not data:
            return extraction_result(
                document_type="html",
                method="beautifulsoup4/html.parser",
                version=self.version,
                profile=self.profile,
            )
        blocks: list[ContentBlock] = []
        warnings: list[str] = []
        errors: list[str] = []
        metadata = empty_metadata()
        incomplete = False
        encoding = None

        def warn(code: str, *, loss: bool = False):
            nonlocal incomplete
            if code not in warnings:
                warnings.append(code)
            incomplete |= loss

        def emit(kind, level, text):
            if text.strip():
                text = text.strip("\r\n ") if kind == "table" else text.strip()
                blocks.append(ContentBlock(kind, level, text))

        def table(tag):
            warn("html_table_text_only")
            rows = tag.find_all("tr")
            cells = tag.find_all(["th", "td"])
            complex_table = (
                tag.find("table") is not None
                or not rows
                or not cells
                or len(cells)
                != sum(len(row.find_all(["th", "td"], recursive=False)) for row in rows)
                or any(
                    _visible_string(node)
                    and str(node).strip()
                    and node.find_parent(["th", "td", "caption"]) is None
                    for node in tag.descendants
                )
                or any(
                    cell.get("rowspan", "1") != "1"
                    or cell.get("colspan", "1") != "1"
                    or cell.find(list(_BOUNDARIES | {"br"})) is not None
                    for cell in cells
                )
                or len({len(row.find_all(["th", "td"], recursive=False)) for row in rows}) > 1
            )
            if complex_table:
                warn("html_table_structure_lost", loss=True)
                # One traversal retains nested table text once, in DOM order.
                parts = []
                for node in tag.descendants:
                    if _visible_string(node):
                        parts.append(re.sub(r"\s+", " ", str(node)))
                    elif isinstance(node, Tag) and node.name in _BOUNDARIES | {
                        "tr",
                        "caption",
                        "br",
                    }:
                        parts.append("\n")
                    elif isinstance(node, Tag) and node.name in {"td", "th"}:
                        parts.append("\t")
                emit("table", None, "".join(parts))
            else:
                lines = []
                for node in tag.find_all(["caption", "tr"]):
                    if node.name == "caption":
                        lines.append(_flow_text(node))
                    else:
                        lines.append(
                            "\t".join(
                                _flow_text(cell)
                                for cell in node.find_all(["th", "td"], recursive=False)
                            )
                        )
                emit("table", None, "\n".join(lines))

        def walk(container, kind="text", level=None, depth=0):
            parts = []

            def flush():
                emit(kind, level, re.sub(r"[ \t\r\f\v]+", " ", "".join(parts)))
                parts.clear()

            def visit(node):
                if _visible_string(node):
                    parts.append(re.sub(r"\s+", " ", str(node)))
                elif isinstance(node, Tag):
                    name = node.name
                    if name == "br":
                        parts.append("\n")
                    elif name in _BOUNDARIES:
                        flush()
                        if name == "table":
                            table(node)
                        elif name == "pre":
                            emit("text", None, node.get_text())
                        elif name in _HEADINGS:
                            walk(node, "heading", int(name[1]), depth)
                        elif name in {"ul", "ol"}:
                            walk(node, "text", None, depth + 1)
                        elif name == "li":
                            walk(node, "list_item", max(depth, 1), depth)
                        elif name == "p" and kind != "list_item":
                            walk(node, "paragraph", None, depth)
                        else:
                            walk(node, kind, level, depth)
                    else:
                        for child in node.children:
                            visit(child)

            for node in container.children:
                visit(node)
            flush()

        try:
            soup = BeautifulSoup(data, "html.parser")
            encoding = soup.original_encoding
            if soup.contains_replacement_characters:
                warn("html_encoding_replacement", loss=True)
            if encoding and encoding.lower().replace("_", "-") not in {"utf-8", "ascii"}:
                warn("html_non_utf8_encoding_detected")
            if soup.title:
                metadata["title"] = _flow_text(soup.title) or None
            html = soup.find("html")
            if html and isinstance(html.get("lang"), str):
                metadata["language"] = html["lang"].strip() or None
            authors = []
            for meta in soup.find_all("meta"):
                value = meta.get("content")
                if not isinstance(value, str) or not value.strip():
                    continue
                if str(meta.get("name", "")).lower() == "author":
                    authors.append(value.strip())
                if (
                    meta.get("property") == "article:published_time"
                    or meta.get("itemprop") == "datePublished"
                ):
                    metadata["published_on"] = value.strip()
            metadata["authors"] = authors or None
            for node in soup.select(
                "script, style, head, title, meta, link, nav, form, button, input, select, "
                "textarea, template, "
                'noscript, [role="navigation"], [hidden], [aria-hidden="true"]'
            ):
                # A selected ancestor may already have removed its descendants.
                if node.parent is not None:
                    node.decompose()
            for node in soup.find_all(
                ["img", "svg", "canvas", "object", "iframe", "video", "audio"]
            ):
                if node.parent is not None:
                    warn("html_nontext_content_omitted", loss=True)
                    node.decompose()
            walk(soup)
        except Exception:
            # Parser failures are isolated; never expose raw document/exception text.
            errors.append("html_parser_error")
            warn("html_incomplete_parse", loss=True)
        return extraction_result(
            document_type="html",
            method="beautifulsoup4/html.parser",
            version=self.version,
            profile=self.profile,
            blocks=blocks,
            warnings=warnings,
            errors=errors,
            incomplete=incomplete,
            metadata=metadata,
            source_encoding=encoding,
        )
