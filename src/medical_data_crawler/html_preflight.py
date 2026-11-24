"""Read-only, offline observations for a single local HTML original."""

import os
import re
import stat
from collections import Counter
from collections.abc import Collection
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

INSPECTOR_VERSION = "0.1.0"
DEFAULT_MAX_BYTES = 1024 * 1024
MAX_INPUT_BYTES = 4 * DEFAULT_MAX_BYTES
HTTP_EVIDENCE_FIELDS = (
    "content_type",
    "status_code",
    "redirect_chain",
    "final_destination",
    "response_headers",
)
_CHARSETS = {
    "utf-8": "utf-8",
    "utf8": "utf-8",
    "ascii": "ascii",
    "us-ascii": "ascii",
    "windows-1252": "cp1252",
    "cp1252": "cp1252",
    "iso-8859-1": "iso8859-1",
    "latin1": "iso8859-1",
    "utf-16": "utf-16",
    "utf-16le": "utf-16-le",
    "utf-16be": "utf-16-be",
    "utf-32": "utf-32",
    "utf-32le": "utf-32-le",
    "utf-32be": "utf-32-be",
}
# Check longer signatures before their prefixes.
_BOMS = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
    (b"\xef\xbb\xbf", "utf-8"),
)
_META_CHARSET = re.compile(r"""\bcharset\s*=\s*["']?([\w.-]{1,40})(?![\w.-])""", re.I)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
_URL_CONTROLS = str.maketrans("", "", "\r\n\t")
_SRCSET_URL = re.compile(r"[^,\t\n\f\r ][^\t\n\f\r ]*")
_CSS_URL = re.compile(
    r"(?<![\w-])(?:(@import\s+)(?:url\(\s*)?|url\(\s*)"
    r"""(?:"([^"]*)"|'([^']*)'|([^\s)'";][^\s)'"]*))""",
    re.I,
)
_PRIVACY = re.compile(
    r"\b(?:mrn|ssn|dob|patient[\s_-]+(?:name|id|identifier)|medical[\s_-]+record|"
    r"date[\s_-]+of[\s_-]+birth)\b|"
    r"(?<![\w.%+-])[\w.%+-]{1,64}@[\w.-]{1,253}\.[a-z]{2,24}\b",
    re.I,
)
_COUNTED_TAGS = {
    "object": "object_element",
    "embed": "embed_element",
    "svg": "inline_svg",
    "frame": "frame",
    "iframe": "iframe",
    "template": "template_element",
    "form": "form",
    "input": "form_field",
    "textarea": "form_field",
    "select": "form_field",
}
_URL_ATTRIBUTES = {
    "src",
    "href",
    "xlink:href",
    "data",
    "poster",
    "background",
    "action",
    "formaction",
    "srcset",
    "imagesrcset",
    "ping",
    "cite",
    "longdesc",
    "manifest",
    "codebase",
}
_REFERENCE_CATEGORIES = {
    ("script", "src"): "script_reference",
    ("script", "href"): "script_reference",
    ("script", "xlink:href"): "script_reference",
    ("img", "src"): "image_reference",
    ("image", "href"): "image_reference",
    ("image", "xlink:href"): "image_reference",
    ("video", "poster"): "image_reference",
    ("audio", "src"): "media_reference",
    ("video", "src"): "media_reference",
    ("source", "src"): "media_reference",
    ("track", "src"): "media_reference",
    ("embed", "src"): "media_reference",
    ("object", "data"): "media_reference",
}
_PRELOAD_CATEGORIES = {
    "image": "image_reference",
    "style": "stylesheet",
    "script": "script_reference",
    "audio": "media_reference",
    "video": "media_reference",
    "track": "media_reference",
}
_HIGH_PRIORITY = {
    "inline_script",
    "script_reference",
    "inline_svg",
    "iframe",
    "iframe_srcdoc",
    "frame",
    "object_element",
    "embed_element",
    "data_url",
    "base64_data_url",
    "event_handler",
    "javascript_url",
    "meta_refresh",
    "privacy_indicator",
    "hidden_content",
}
_MANUAL_REVIEW = (
    "VERIFY_HTTP_EVIDENCE",
    "REVIEW_EMBEDDED_AND_THIRD_PARTY_ASSETS",
    "REVIEW_PRIVACY_AND_PHI",
    "REVIEW_ACCESS_AND_ASSET_RIGHTS",
)


class _InputRejected(Exception):
    def __init__(self, code: str, size: int | None = None):
        self.code = code
        self.size = size


def _local_path(value: str | Path) -> Path:
    raw = os.fspath(value)
    if not raw or raw.startswith(("//", "\\\\")) or "://" in raw:
        raise _InputRejected("NONLOCAL_OR_INVALID_PATH")
    path = Path(raw)
    if os.name == "nt" and (
        (path.drive and not path.root)
        or any(
            ":" in part or Path(part).is_reserved() for part in path.parts if part != path.anchor
        )
    ):
        raise _InputRejected("NONLOCAL_OR_INVALID_PATH")
    path = path.absolute()
    if os.name == "nt":
        from ctypes import c_wchar_p, windll

        # Drive letters can identify mapped network shares as well as local disks.
        if (
            path.drive.startswith("\\\\")
            or windll.kernel32.GetDriveTypeW(c_wchar_p(path.anchor)) == 4  # DRIVE_REMOTE
        ):
            raise _InputRejected("NONLOCAL_OR_INVALID_PATH")
    return path


def _read_original(value: str | Path, limit: int) -> bytes:
    path = _local_path(value)
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise _InputRejected("LINK_OR_REPARSE_POINT")
    if not stat.S_ISREG(info.st_mode):
        raise _InputRejected("NOT_REGULAR_FILE")
    if info.st_size > limit:
        raise _InputRejected("INPUT_TOO_LARGE", info.st_size)

    flags = os.O_RDONLY
    for name in ("O_BINARY", "O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, name, 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(info, opened):
            raise _InputRejected("INPUT_CHANGED")
        if opened.st_size > limit:
            raise _InputRejected("INPUT_TOO_LARGE", opened.st_size)
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(data) > limit:
            raise _InputRejected("INPUT_TOO_LARGE")
        if (len(data), after.st_size, after.st_mtime_ns) != (
            opened.st_size,
            opened.st_size,
            opened.st_mtime_ns,
        ):
            raise _InputRejected("INPUT_CHANGED")
    return data


def _srcset_urls(value: str):
    pos = 0
    while match := _SRCSET_URL.search(value, pos):
        url = match.group()
        yield url.rstrip(",")
        pos = match.end()
        if not url.endswith(","):
            separator = value.find(",", pos)
            if separator == -1:
                return
            pos = separator + 1


class _Scanner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.counts = Counter()
        self.charsets = set()
        self.issues = set()
        self.has_elements = False

    def _reference(self, value: str, category: str | None = None):
        url = value.strip().translate(_URL_CONTROLS)
        if not url:
            return
        if category:
            self.counts[category] += 1
        prefix = url[:11].lower()
        if prefix.startswith("data:"):
            self.counts["data_url"] += 1
            metadata, comma, _ = url.partition(",")
            if comma and metadata.lower().endswith(";base64"):
                self.counts["base64_data_url"] += 1
        elif prefix.startswith("javascript:"):
            self.counts["javascript_url"] += 1
        elif prefix.startswith(("https:", "http:", "//")) and category:
            self.counts[f"remote_{category}"] += 1

    def _css(self, value: str):
        for match in _CSS_URL.finditer(value):
            imported, double, single, bare = match.groups()
            category = "stylesheet" if imported else "css_asset_reference"
            self._reference(double or single or bare or "", category)

    def handle_data(self, data):
        if self.cdata_elem == "style":
            self._css(data)
        if _PRIVACY.search(data):
            self.counts["privacy_indicator"] += 1

    def handle_comment(self, data):
        if _PRIVACY.search(data):
            self.counts["privacy_indicator"] += 1

    def unknown_decl(self, data):
        self.issues.add("UNRECOGNIZED_MARKUP_DECLARATION")

    def handle_starttag(self, tag, attrs):
        self.has_elements = True
        attrs_by_name = {name: value or "" for name, value in reversed(attrs)}
        if len(attrs_by_name) != len(attrs):
            self.issues.add("DUPLICATE_ATTRIBUTES")
        if tag in _COUNTED_TAGS:
            self.counts[_COUNTED_TAGS[tag]] += 1
        if tag == "script" and not any(
            attrs_by_name.get(name, "").strip() for name in ("src", "href", "xlink:href")
        ):
            self.counts["inline_script"] += 1
        if tag == "style" or "style" in attrs_by_name:
            self.counts["inline_style"] += 1
        if tag == "iframe" and "srcdoc" in attrs_by_name:
            self.counts["iframe_srcdoc"] += 1
        if tag == "base" and "href" in attrs_by_name:
            self.counts["base_href"] += 1
        if tag == "meta":
            self._meta(attrs_by_name)
        kind = attrs_by_name.get("type", "").strip().lower()
        if (
            "hidden" in attrs_by_name
            or attrs_by_name.get("aria-hidden", "").lower() == "true"
            or (tag == "input" and kind == "hidden")
        ):
            self.counts["hidden_content"] += 1

        rel = attrs_by_name.get("rel", "").lower().split() if tag == "link" else ()
        for name, raw in attrs:
            value = raw or ""
            if _PRIVACY.search(name) or _PRIVACY.search(value):
                self.counts["privacy_indicator"] += 1
            if name.startswith("on") and value:
                self.counts["event_handler"] += 1
            if name == "style":
                self._css(value)
            if name in {"srcset", "imagesrcset"}:
                for url in _srcset_urls(value):
                    self._reference(url, "image_reference")
            elif name in _URL_ATTRIBUTES:
                category = _REFERENCE_CATEGORIES.get((tag, name))
                if tag == "link" and name == "href":
                    if "stylesheet" in rel:
                        category = "stylesheet"
                    elif "icon" in rel:
                        category = "image_reference"
                    elif "modulepreload" in rel:
                        category = "script_reference"
                    elif "preload" in rel:
                        category = _PRELOAD_CATEGORIES.get(
                            attrs_by_name.get("as", "").strip().lower()
                        )
                elif tag == "input" and kind == "image" and name == "src":
                    category = "image_reference"
                self._reference(value, category)

    def _meta(self, attrs):
        equiv = attrs.get("http-equiv", "").strip().lower()
        if equiv == "refresh":
            self.counts["meta_refresh"] += 1
        if "charset" in attrs:
            self.charsets.add(_CHARSETS.get(attrs["charset"].strip().lower(), "UNSUPPORTED"))
        if equiv == "content-type" and (match := _META_CHARSET.search(attrs.get("content", ""))):
            self.charsets.add(_CHARSETS.get(match[1].lower(), "UNSUPPORTED"))


def _scan(scanner: _Scanner, text: str, *, prefix: bool = False):
    try:
        scanner.feed(text)
        if not prefix:
            if scanner.rawdata.startswith("<") or scanner.cdata_elem:
                scanner.issues.add("UNFINISHED_MARKUP")
            else:
                scanner.close()
    except (AssertionError, ValueError, RecursionError):
        scanner.issues.add("HTML_PARSER_ERROR")


def _inspect_bytes(data: bytes, report: dict) -> None:
    bom, byte_encoding = next(((b, enc) for b, enc in _BOMS if data.startswith(b)), (b"", None))
    body = data[len(bom) :]
    probe = _Scanner()
    # An ASCII-compatible prefix probe avoids guessing a codec from arbitrary bytes.
    if byte_encoding in {None, "utf-8"}:
        _scan(probe, body[:1024].decode("latin1"), prefix=True)
    declared = next(iter(probe.charsets)) if len(probe.charsets) == 1 else None
    encoding = byte_encoding or (
        declared if declared in {"utf-8", "ascii", "iso8859-1", "cp1252"} else "utf-8"
    )

    issues = set()
    try:
        decoded = body.decode(encoding)
    except UnicodeDecodeError:
        issues.add("DECODE_REPLACEMENT")
        decoded = body.decode(encoding, errors="replace")
    if _CONTROL.search(decoded):
        issues.add("UNEXPECTED_CONTROL_CHARACTERS")

    scanner = _Scanner()
    _scan(scanner, decoded)
    charsets = scanner.charsets | probe.charsets
    supported = charsets - {"UNSUPPORTED"}
    if "UNSUPPORTED" in charsets:
        issues.add("UNSUPPORTED_CHARSET")
    compatible = {encoding, encoding.removesuffix("-le").removesuffix("-be")}
    if supported - compatible:
        issues.add("CHARSET_NOT_USED")
        if len(supported) > 1:
            issues.add("CONFLICTING_CHARSETS")
    if not scanner.has_elements:
        issues.add("NO_HTML_ELEMENTS")
    issues.update(scanner.issues)

    status = "PARSED"
    if "HTML_PARSER_ERROR" in issues or not scanner.has_elements:
        status = "FAILED"
    elif issues:
        status = "PARTIAL"
    report.update(
        byte_size=len(data),
        sha256=sha256(data).hexdigest(),
        parse_status=status,
        encoding={"declared": sorted(charsets), "used": encoding, "bom": byte_encoding},
        counts=dict(sorted(scanner.counts.items())),
        findings=[{"code": code, "priority": "HIGH"} for code in sorted(issues)]
        + [
            {"code": code.upper(), "priority": "HIGH" if code in _HIGH_PRIORITY else "REVIEW"}
            for code in sorted(scanner.counts)
        ],
    )


def inspect_html(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    supplied_http_fields: Collection[str] = (),
) -> dict:
    """Inspect local bytes; supplied HTTP field names indicate presence, never verification."""
    report = {
        "inspector_version": INSPECTOR_VERSION,
        "inspected_at": datetime.now(UTC).isoformat(),
        "byte_size": None,
        "sha256": None,
        "parse_status": "NOT_ATTEMPTED",
        "encoding": None,
        "counts": {},
        "findings": [],
        "http_evidence": {
            field: {"status": "NOT VERIFIED", "supplied": field in supplied_http_fields}
            for field in HTTP_EVIDENCE_FIELDS
        },
        "missing_evidence": [f for f in HTTP_EVIDENCE_FIELDS if f not in supplied_http_fields],
        "limitations": ["STATIC_TOKEN_SCAN_ONLY", "PRIVACY_INDICATORS_ADVISORY"],
        "manual_review": list(_MANUAL_REVIEW),
        "review_readiness": "INSPECTION_INCOMPLETE",
    }
    try:
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_INPUT_BYTES:
            raise _InputRejected("INVALID_SIZE_LIMIT")
        data = _read_original(path, max_bytes)
    except _InputRejected as exc:
        report["byte_size"] = exc.size
        report["findings"].append({"code": exc.code, "priority": "HIGH"})
    except (OSError, TypeError, ValueError):
        report["findings"].append({"code": "INPUT_READ_ERROR", "priority": "HIGH"})
    else:
        _inspect_bytes(data, report)
        if report["parse_status"] == "PARSED":
            report["review_readiness"] = "REVIEW_REQUIRED"
    return report
