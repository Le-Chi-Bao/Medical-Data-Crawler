import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from medical_data_crawler import _intake_files as files
from medical_data_crawler.integrity import sha256_stream


@pytest.mark.parametrize("dry_run", [False, True])
def test_snapshot_spills_only_during_live_import(tmp_path, monkeypatch, dry_run):
    source = tmp_path / "fixture.html"
    document = b"<p>Fixture</p>" + b" " * (1024 * 1024)
    source.write_bytes(document)
    temp_lookups = []

    def temp_directory():
        temp_lookups.append(True)
        return tmp_path

    monkeypatch.setattr(files, "_local_temp_directory", temp_directory)
    with source.open("rb") as original:
        expected = sha256_stream(original)
    with files.snapshot_document(
        str(source), (tmp_path,), "html", len(document), expected, dry_run=dry_run
    ) as (snapshot, digest):
        assert snapshot.tell() == 0
        assert digest == sha256_stream(snapshot) == expected
    assert list(tmp_path.iterdir()) == [source]
    assert bool(temp_lookups) is not dry_run


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32"])
def test_snapshot_accepts_bom_and_html_fragment(tmp_path, encoding):
    source = tmp_path / "fixture.htm"
    document = "<article><p>Fixture</p></article>".encode(encoding)
    source.write_bytes(document)
    with files.snapshot_document(
        str(source), (tmp_path,), "html", len(document), None, dry_run=True
    ) as (snapshot, _):
        assert snapshot.read() == document


@pytest.mark.parametrize(
    ("document", "code"),
    [
        (b"<!-- <article><p>Only a comment</p></article> -->", "format_mismatch"),
        (b'<p>Fixture</p><img src="', "invalid_document"),
        (b"<p>Fixture</p><!--" + b"x" * 131072, "invalid_document"),
    ],
)
def test_snapshot_checks_html_structure(tmp_path, document, code):
    source = tmp_path / "fixture.html"
    source.write_bytes(document)
    with pytest.raises(files.IntakeFileError, match=code):
        with files.snapshot_document(str(source), (tmp_path,), "html", len(document), None):
            pytest.fail("invalid snapshot was accepted")


def test_parser_diagnostics_are_redacted_only_during_intake(caplog):
    logger = logging.getLogger("pypdf.synthetic")
    old_factory = logging.getLogRecordFactory()
    with ThreadPoolExecutor(max_workers=1) as pool, files.private_pdf_diagnostics():
        logger.warning("private %s", "synthetic-secret")
        pool.submit(logger.warning, "outside the intake context").result()
    assert logging.getLogRecordFactory() is old_factory
    assert caplog.messages == ["internal_intake_parser_diagnostic", "outside the intake context"]


@pytest.mark.skipif(os.name != "nt", reason="Windows drive classification")
def test_mapped_windows_drive_is_denied_before_filesystem_lookup(monkeypatch):
    monkeypatch.setattr(
        files, "_windows_api", lambda: (SimpleNamespace(GetDriveTypeW=lambda _: 4), None)
    )

    def unexpected_stat(*args, **kwargs):
        pytest.fail("mapped drive reached filesystem lookup")

    monkeypatch.setattr(Path, "lstat", unexpected_stat)
    with pytest.raises(files.IntakeFileError, match="network_path_disallowed"):
        files.check_local_path("Z:/fixture.html")
