import json
import os
import runpy
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from medical_data_crawler.html_preflight import HTTP_EVIDENCE_FIELDS, MAX_INPUT_BYTES, inspect_html

_CLI = Path(__file__).parents[2] / "scripts/inspect_html_preflight.py"


@pytest.fixture
def original(tmp_path):
    def create(content):
        path = tmp_path / "synthetic-fixture.html"
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path

    return create


def _codes(report):
    return {finding["code"] for finding in report["findings"]}


def test_plain_html_reports_exact_bytes_and_requires_manual_review(original):
    data = b'<!doctype html>\r\n<meta charset="UTF-8"><p>Synthetic &amp; local.</p>'
    result = inspect_html(original(data), max_bytes=len(data))
    assert result["byte_size"] == len(data)
    assert result["sha256"] == sha256(data).hexdigest()
    assert result["inspector_version"]
    assert datetime.fromisoformat(result["inspected_at"]).utcoffset() == timedelta(0)
    assert result["parse_status"] == "PARSED"
    assert result["encoding"] == {"declared": ["utf-8"], "used": "utf-8", "bom": None}
    assert result["counts"] == {}
    assert result["findings"] == []
    assert "REVIEW_PRIVACY_AND_PHI" in result["manual_review"]
    assert result["review_readiness"] == "REVIEW_REQUIRED"


def test_images_resources_and_media(original):
    report = inspect_html(
        original(
            '<base href="https://synthetic.invalid/">'
            '<img src="relative.png" srcset="//synthetic.invalid/image.png 1x, local.png 2x">'
            '<img src="https://synthetic.invalid/other.png">'
            '<link rel="stylesheet" href="https://synthetic.invalid/default.css">'
            '<style>@import "//synthetic.invalid/additional.css"; '
            "body { background: url(https://synthetic.invalid/background.png) }</style>"
            '<video src="//synthetic.invalid/video" poster="local.png"></video>'
            '<source src="relative.mp4"><audio src="https://synthetic.invalid/audio"></audio>'
            '<link rel="preload" as="image" href="https://synthetic.invalid/preloaded.png">'
            '<meta http-equiv="Refresh" content="3; url=https://synthetic.invalid/">'
        )
    )
    assert report["counts"] == {
        "base_href": 1,
        "css_asset_reference": 1,
        "image_reference": 6,
        "inline_style": 1,
        "media_reference": 3,
        "meta_refresh": 1,
        "remote_css_asset_reference": 1,
        "remote_image_reference": 3,
        "remote_media_reference": 2,
        "remote_stylesheet": 2,
        "stylesheet": 2,
    }


def test_inline_and_referenced_active_content(original):
    result = inspect_html(
        original(
            '<script>const synthetic = "<img src=ignored.png>";</script>'
            '<script src="https://synthetic.invalid/app.js"></script>'
            '<script src="relative.js"></script>'
            '<svg><image href="data:image/png;base64,U1lOVEhFVElD"/></svg>'
            '<img srcset="data:image/png;base64,U1lOVEhFVElD 1x, relative.png 2x">'
            '<p style="background: url(data:image/png;base64,U1lOVEhFVElD)"></p>'
            '<iframe srcdoc="&lt;script>nested&lt;/script>"></iframe>'
            '<embed src="data:text/plain,synthetic"><object data="relative.bin"></object>'
            '<a onclick="synthetic()" href="java&#x09;script:synthetic()">Synthetic</a>'
        )
    )
    counts = result["counts"]
    assert counts["inline_script"] == 1
    assert counts["script_reference"] == 2
    assert counts["remote_script_reference"] == 1
    assert counts["inline_svg"] == 1
    assert counts["data_url"] == 4
    assert counts["base64_data_url"] == 3
    assert counts["iframe"] == counts["iframe_srcdoc"] == 1
    assert counts["object_element"] == counts["embed_element"] == 1
    assert counts["event_handler"] == counts["javascript_url"] == 1
    assert "U1lOVEhFVElD" not in json.dumps(result)


@pytest.mark.parametrize(
    ("data", "code", "status"),
    [
        (b'<p>fixture <img src="truncated', "UNFINISHED_MARKUP", "PARTIAL"),
        (b"<script>truncated", "UNFINISHED_MARKUP", "PARTIAL"),
        (b"<p><img src=a src=b>", "DUPLICATE_ATTRIBUTES", "PARTIAL"),
        (b'<meta charset="utf-8"><p>Caf\xe9</p>', "DECODE_REPLACEMENT", "PARTIAL"),
        (b'\xef\xbb\xbf<meta charset="windows-1252"><p>A</p>', "CHARSET_NOT_USED", "PARTIAL"),
        (b'<meta charset="synthetic-private-label"><p>A</p>', "UNSUPPORTED_CHARSET", "PARTIAL"),
        (
            b'<meta charset="utf8"><meta charset="latin1"><p>A</p>',
            "CONFLICTING_CHARSETS",
            "PARTIAL",
        ),
        (b"<p>\x00fixture</p>", "UNEXPECTED_CONTROL_CHARACTERS", "PARTIAL"),
        (b"%PDF-1.7\x00\xff", "NO_HTML_ELEMENTS", "FAILED"),
        (b"", "NO_HTML_ELEMENTS", "FAILED"),
    ],
)
def test_incomplete_scan_retains_original_digest(original, data, code, status):
    result = inspect_html(original(data))
    assert result["parse_status"] == status
    assert result["review_readiness"] == "INSPECTION_INCOMPLETE"
    assert code in _codes(result)
    assert result["sha256"] == sha256(data).hexdigest()
    assert "synthetic-private-label" not in json.dumps(result)


@pytest.mark.parametrize(
    ("data", "declared", "used"),
    [
        (
            b'<meta http-equiv="content-type" content="text/html; charset=windows-1252">'
            b"<p>Caf\xe9</p>",
            "cp1252",
            "cp1252",
        ),
        (
            b"\xff\xfe" + '<meta charset="UTF-16"><p>A</p>'.encode("utf-16-le"),
            "utf-16",
            "utf-16-le",
        ),
    ],
)
def test_supported_encoding(original, data, declared, used):
    result = inspect_html(original(data))
    assert result["parse_status"] == "PARSED"
    assert result["encoding"]["declared"] == [declared]
    assert result["encoding"]["used"] == used


def test_parser_failure_is_sanitized(original, monkeypatch):
    def fail(*args):
        raise ValueError("synthetic parser exception secret")

    monkeypatch.setattr("medical_data_crawler.html_preflight.HTMLParser.feed", fail)
    result = inspect_html(original("<p>Synthetic</p>"))
    assert result["parse_status"] == "FAILED"
    assert "HTML_PARSER_ERROR" in _codes(result)
    assert "synthetic parser exception secret" not in json.dumps(result)


def test_oversize_is_rejected_before_open(original, monkeypatch):
    path = original("<p>Synthetic</p>")

    def blocked(*args, **kwargs):
        pytest.fail("Oversized file must not be opened")

    monkeypatch.setattr(os, "open", blocked)
    result = inspect_html(path, max_bytes=4)
    assert result["byte_size"] == path.stat().st_size
    assert result["sha256"] is None
    assert result["parse_status"] == "NOT_ATTEMPTED"
    assert _codes(result) == {"INPUT_TOO_LARGE"}
    assert _codes(inspect_html(path, max_bytes=MAX_INPUT_BYTES + 1)) == {"INVALID_SIZE_LIMIT"}


def test_file_growth_after_open_is_bounded(original, monkeypatch):
    path = original("<p>Synthetic</p>")
    limit = path.stat().st_size
    real_fdopen = os.fdopen

    @contextmanager
    def grow_on_read(fd, mode):
        with real_fdopen(fd, mode) as stream:

            def read(size):
                assert size == limit + 1
                with path.open("ab") as append:
                    append.write(b"more synthetic bytes")
                return stream.read(size)

            yield SimpleNamespace(read=read, fileno=stream.fileno)

    monkeypatch.setattr(os, "fdopen", grow_on_read)
    report = inspect_html(path, max_bytes=limit)
    assert _codes(report) == {"INPUT_TOO_LARGE"}
    assert report["sha256"] is None


def test_symlink_is_rejected(original):
    path = original("<p>Synthetic</p>")
    link = path.with_name("link.html")
    try:
        link.symlink_to(path)
    except OSError as exc:
        if getattr(exc, "winerror", None) != 1314:
            raise
        pytest.skip("Windows user is missing symlink creation privilege")
    result = inspect_html(link)
    assert result["sha256"] is None
    assert _codes(result) == {"LINK_OR_REPARSE_POINT"}


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junctions only")
def test_windows_directory_junction_is_rejected(original):
    from _winapi import CreateJunction

    path = original("<p>Synthetic</p>")
    target = path.parent / "target"
    target.mkdir()
    (target / path.name).write_bytes(path.read_bytes())
    junction = path.parent / "junction"
    CreateJunction(str(target), str(junction))
    try:
        result = inspect_html(junction / path.name)
        assert result["sha256"] is None
        assert _codes(result) == {"LINK_OR_REPARSE_POINT"}
    finally:
        junction.rmdir()


def test_directory_missing_and_nonlocal_paths_are_rejected(tmp_path, monkeypatch):
    assert _codes(inspect_html(tmp_path)) == {"NOT_REGULAR_FILE"}
    assert _codes(inspect_html(tmp_path / "missing.html")) == {"INPUT_READ_ERROR"}

    def blocked(*args, **kwargs):
        pytest.fail("Nonlocal locator must not reach the filesystem")

    monkeypatch.setattr(Path, "lstat", blocked)
    for value in ("https://synthetic.invalid/token", r"\\synthetic.invalid\share\fixture.html"):
        result = inspect_html(value)
        assert _codes(result) == {"NONLOCAL_OR_INVALID_PATH"}
        assert "synthetic.invalid" not in json.dumps(result)


def test_http_evidence_is_never_inferred_or_verified(original):
    path = original('<meta http-equiv="content-type" content="text/html; charset=utf-8">')
    missing = inspect_html(path)
    assert missing["missing_evidence"] == list(HTTP_EVIDENCE_FIELDS)
    assert missing["http_evidence"]["content_type"] == {"status": "NOT VERIFIED", "supplied": False}

    supplied = inspect_html(path, supplied_http_fields=("content_type", "status_code", "synthetic"))
    assert supplied["missing_evidence"] == list(HTTP_EVIDENCE_FIELDS[2:])
    assert supplied["http_evidence"]["content_type"] == {"status": "NOT VERIFIED", "supplied": True}
    assert all(field["status"] == "NOT VERIFIED" for field in supplied["http_evidence"].values())
    assert "synthetic" not in json.dumps(supplied)


def test_cli_is_offline_read_only_and_suppresses_sensitive_strings(original, monkeypatch, capsys):
    path = original(
        '<form><input name="patient_name" value="SYNTHETIC_NAME">'
        '<input type="hidden" value="SYNTHETIC_MRN"></form>'
        '<img src="https://synthetic.invalid/photo?token=SYNTHETIC_TOKEN">'
        "<script>const value = 'SYNTHETIC_SCRIPT';</script>"
        "<p>Email: SYNTHETIC_EMAIL@example.invalid</p><!-- DOB: SYNTHETIC_DOB -->"
    )
    data = path.read_bytes()
    before = path.stat()
    real_open = os.open

    def read_only(file, flags, *args, **kwargs):
        assert file == path
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        return real_open(file, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", read_only)
    monkeypatch.chdir(path.parent)
    monkeypatch.setattr(sys, "argv", [str(_CLI), str(path), "--http-evidence-field", "status_code"])
    with pytest.raises(SystemExit) as exit_info:
        # Run in-process so the repository's socket and DNS guard covers the CLI too.
        runpy.run_path(str(_CLI), run_name="__main__")
    assert exit_info.value.code == 0
    captured = capsys.readouterr()
    assert not captured.err
    assert "SYNTHETIC_" not in captured.out
    assert str(path) not in captured.out
    result = json.loads(captured.out)
    assert result["counts"]["privacy_indicator"] == 3
    assert result["counts"]["hidden_content"] == 1
    assert result["http_evidence"]["status_code"]["supplied"] is True
    assert path.read_bytes() == data
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert list(path.parent.iterdir()) == [path]


def test_cli_usage_errors_do_not_echo_argument_values(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(_CLI), "--http-evidence-field", "SYNTHETIC_SECRET"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(_CLI), run_name="__main__")
    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == "INVALID_ARGUMENTS (see --help)\n"
    assert not captured.out
