import hashlib
import json
import logging
import os
import socket
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace

import pytest

from medical_data_crawler import _intake_files, export, internal_import
from medical_data_crawler.contract import validate_record
from medical_data_crawler.export import ExportError, validate_manifest, verify_batch
from medical_data_crawler.html_extraction import HTMLExtractor
from medical_data_crawler.internal_import import InternalIntakeGateway, parse_authorizations
from medical_data_crawler.internal_import_cli import main as intake_cli
from medical_data_crawler.pdf_extraction import PDFExtractor
from medical_data_crawler.provenance import ProvenanceStore, document_id
from medical_data_crawler.storage import ArtifactStore

HTML = b"<!doctype html><html><title>Fixture</title><body><h1>Synthetic HTML</h1></body></html>"


def request(path, key="synthetic-document", **overrides):
    return {
        "source_id": "internal-fixture",
        "logical_key": key,
        "locator": f"internal:{key}",
        "local_path": str(path),
        "format": "html",
        "provider_ref": "provider-fixture",
        "authorization_ref": f"approval-{key}",
        "allow_store": True,
        "allow_extract": True,
        "access_basis": "internal_authorization",
        **overrides,
    }


def approval(document, **overrides):
    return {
        **document,
        "active": True,
        "expires_at": "2099-01-01T00:00:00Z",
        "operation": "internal_import",
        "allow_read": True,
        **overrides,
    }


def spec(*documents):
    return {"intake_version": "0.1", "documents": list(documents)}


def approvals(*grants):
    return {"authorization_version": "0.1", "authorizations": list(grants)}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def intake(tmp_path):
    inbox = tmp_path / "approved-inbox"
    inbox.mkdir()
    state = tmp_path / "state"

    def gateway(*grants, **options):
        return InternalIntakeGateway(
            approved_roots=(inbox,),
            state_root=state,
            authorizations=parse_authorizations(approvals(*grants)),
            **options,
        )

    return inbox, state, gateway


def test_mixed_batch_exports_verified_records_and_keeps_provenance_for_each_attempt(
    intake, pdf_bytes
):
    inbox, state, gateway = intake
    html_path = inbox / "synthetic-note.htm"
    html_path.write_bytes(HTML)
    duplicate_path = inbox / "copy.html"
    duplicate_path.write_bytes(HTML)
    pdf_path = inbox / "synthetic.pdf"
    pdf_data = pdf_bytes([[(72, 720, "Synthetic PDF")]])
    pdf_path.write_bytes(pdf_data)
    denied_path = inbox / "unapproved.html"
    denied_path.write_bytes(HTML)
    broken_path = inbox / "broken.pdf"
    broken_path.write_bytes(b"%PDF-1.7\ntruncated fixture\n%%EOF\n")

    html_hash = hashlib.sha256(HTML).hexdigest()
    pdf_hash = hashlib.sha256(pdf_data).hexdigest()
    html = request(html_path, "html", format="htm", expected_sha256=html_hash)
    duplicate = request(duplicate_path, "duplicate")
    denied = request(denied_path, "denied")
    broken = request(broken_path, "broken", format="pdf")
    pdf = request(pdf_path, "pdf", format="pdf")
    importer = gateway(*(approval(item) for item in (html, duplicate, broken, pdf)))
    result = importer.run(spec(html, denied, duplicate, broken, pdf))
    assert result.report["summary"] == {
        "total": 5,
        "failed": 2,
        "stored_only": 0,
        "exported": 3,
        "validated": 0,
    }
    items = result.report["items"]
    assert [item["input_index"] for item in items] == list(range(5))
    assert [item["status"] for item in items] == [
        "exported",
        "failed",
        "exported",
        "failed",
        "exported",
    ]
    assert items[1]["code"] == "authorization_missing"
    assert items[3]["code"] == "invalid_document"
    assert all(items[index]["event_id"] is None for index in (1, 3))
    assert len(list((state / "provenance").glob("*.json"))) == 3
    assert {path.name for path in (state / "originals").iterdir()} == {html_hash, pdf_hash}
    assert (state / "originals" / html_hash).read_bytes() == html_path.read_bytes() == HTML
    assert (state / "originals" / pdf_hash).read_bytes() == pdf_path.read_bytes() == pdf_data
    assert items[0]["document_id"] == document_id(html["source_id"], html["logical_key"])
    assert items[0]["document_id"] != items[2]["document_id"]
    assert items[0]["event_id"] != items[2]["event_id"]
    assert items[0]["sha256"] == items[2]["sha256"] == html_hash

    assert result.verification.valid
    manifest = read_json(result.manifest_path)
    validate_manifest(manifest)
    assert manifest["summary"]["total"] == manifest["summary"]["exported"] == 3
    provenance = ProvenanceStore(state / "provenance", ArtifactStore(state / "originals"))
    assert verify_batch(result.manifest_path, provenance).valid
    for item_index, request_doc, media_type, expected_text in [
        (0, html, "text/html", "Synthetic HTML"),
        (2, duplicate, "text/html", "Synthetic HTML"),
        (4, pdf, "application/pdf", "Synthetic PDF"),
    ]:
        item = items[item_index]
        entry = manifest["records"][item["export_input_index"]]
        record = read_json(result.manifest_path.parent / entry["record_path"])
        validate_record(record)
        event = read_json(state / "provenance" / f"{item['event_id']}.json")
        assert event["status"] == "accepted"
        assert event["locator"] == record["source"]["locator"] == request_doc["locator"]
        assert event["document_id"] == record["document_id"] == item["document_id"]
        assert event["sha256"] == record["original"]["sha256"] == item["sha256"]
        assert event["internal"]["authorization_ref"] == request_doc["authorization_ref"]
        assert event["internal"]["provider_ref"] == request_doc["provider_ref"]
        assert event["internal"]["allow_extract"] is True
        assert record["original"]["media_type"] == media_type
        assert record["extraction"]["status"] == "success"
        assert record["rights"]["reuse"] == "unknown"
        assert any(expected_text in block["text"] for block in record["content"])

    repeated = importer.run(spec(html))
    repeated_item = repeated.report["items"][0]
    assert repeated_item["document_id"] == items[0]["document_id"]
    assert repeated_item["event_id"] != items[0]["event_id"]
    assert repeated_item["sha256"] == items[0]["sha256"]
    assert repeated.verification.valid
    assert len(list((state / "originals").iterdir())) == 2
    assert len(list((state / "provenance").glob("*.json"))) == 4


@pytest.mark.parametrize(
    ("grant_overrides", "spec_overrides", "expected"),
    [
        (None, {}, "authorization_missing"),
        ({"expires_at": "2000-01-01T00:00:00Z"}, {}, "authorization_expired"),
        ({"active": False}, {}, "authorization_inactive"),
        ({"logical_key": "other-key"}, {}, "authorization_binding_mismatch"),
        ({"source_id": "internal-other"}, {}, "authorization_binding_mismatch"),
        ({"locator": "internal:other-document"}, {}, "authorization_binding_mismatch"),
        ({"provider_ref": "other-provider"}, {}, "authorization_binding_mismatch"),
        ({"local_path": "unused-fixture.html"}, {}, "authorization_binding_mismatch"),
        ({"operation": "internal_review"}, {}, "authorization_operation_mismatch"),
        ({"allow_read": False}, {}, "read_not_authorized"),
        ({"allow_store": False}, {}, "storage_not_authorized"),
        ({}, {"allow_store": False}, "storage_not_authorized"),
        ({}, {"reuse": "permitted"}, "reuse_not_authorized"),
    ],
)
def test_authorization_denials_happen_before_open_or_store(
    intake, monkeypatch, grant_overrides, spec_overrides, expected
):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    document = request(path)
    grants = () if grant_overrides is None else (approval(document, **grant_overrides),)

    def unexpected_read(*args, **kwargs):
        pytest.fail("Denied intake tried to open an original")

    monkeypatch.setattr(_intake_files, "open_local_binary", unexpected_read)
    result = gateway(*grants).run(spec(dict(document, **spec_overrides)))
    item = result.report["items"][0]
    assert item["status"] == "failed" and item["code"] == expected
    assert item["event_id"] is None and item["sha256"] is None
    assert result.report["summary"]["failed"] == 1
    assert result.manifest_path is None
    assert not state.exists()


@pytest.mark.parametrize("declines_extraction", ["document", "authorization"])
def test_storage_only_never_dispatches_an_extractor(
    intake, pdf_bytes, monkeypatch, declines_extraction
):
    inbox, state, gateway = intake
    path = inbox / "storage-only.pdf"
    data = pdf_bytes([[(72, 720, "Synthetic text never exported")]])
    path.write_bytes(data)
    document = request(path, format="pdf", allow_extract=declines_extraction != "document")
    grant = approval(document, allow_extract=declines_extraction != "authorization")

    def unexpected_extract(*args, **kwargs):
        pytest.fail("Storage-only intake dispatched a text extractor")

    monkeypatch.setattr(HTMLExtractor, "extract", unexpected_extract)
    monkeypatch.setattr(PDFExtractor, "extract", unexpected_extract)
    result = gateway(grant).run(spec(document))
    item = result.report["items"][0]
    assert item["status"] == "stored_only" and item["code"] == "extraction_not_authorized"
    assert item["event_id"] and item["export_input_index"] is None
    assert result.report["summary"]["stored_only"] == 1
    assert result.report["summary"]["exported"] == 0
    assert (state / "originals" / item["sha256"]).read_bytes() == data
    event = read_json(state / "provenance" / f"{item['event_id']}.json")
    assert event["status"] == "accepted" and event["internal"]["allow_extract"] is False
    assert result.manifest_path is None
    assert not (state / "exports").exists()


def test_dry_run_checks_files_without_store_provenance_or_extraction(intake, monkeypatch):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    good = request(path, "valid")
    mismatch = request(path, "bad-checksum", expected_sha256="0" * 64)
    denied = request(path, "denied")

    def unexpected_action(*args, **kwargs):
        pytest.fail("Dry-run performed a persistent action or dispatched a text extractor")

    monkeypatch.setattr(internal_import, "ArtifactStore", unexpected_action)
    monkeypatch.setattr(internal_import, "ProvenanceStore", unexpected_action)
    monkeypatch.setattr(HTMLExtractor, "extract", unexpected_action)
    monkeypatch.setattr(PDFExtractor, "extract", unexpected_action)
    result = gateway(approval(good), approval(mismatch)).run(
        spec(good, mismatch, denied), dry_run=True
    )
    assert [item["status"] for item in result.report["items"]] == ["validated", "failed", "failed"]
    assert [item["code"] for item in result.report["items"]][1:] == [
        "checksum_mismatch",
        "authorization_missing",
    ]
    assert all(item["event_id"] is None for item in result.report["items"])
    assert result.manifest_path is None and result.verification is None
    assert not state.exists()


def test_unsafe_or_invalid_input_files_do_not_leave_artifacts(intake, tmp_path, pdf_bytes):
    inbox, state, gateway = intake
    outside = tmp_path / "outside.html"
    outside.write_bytes(HTML)
    empty = inbox / "empty.html"
    empty.touch()
    unsupported = inbox / "file.text"
    unsupported.write_bytes(HTML)
    wrong_pdf = inbox / "html-in-pdf.pdf"
    wrong_pdf.write_bytes(HTML)
    wrong_html = inbox / "pdf-in-html.html"
    wrong_html.write_bytes(pdf_bytes([[(72, 720, "Fixture")]]))
    oversized = inbox / "big.html"
    oversized.write_bytes(HTML + b" " * 4096)
    directory = inbox / "directory.html"
    directory.mkdir()
    candidates = [
        ("relative.html", {}, "invalid_path"),
        (outside, {}, "path_outside_root"),
        (inbox / ".." / outside.name, {}, "path_outside_root"),
        (r"\\fixture.invalid\share\private.html", {}, "network_path_disallowed"),
        (inbox / "missing.html", {}, "file_not_found"),
        (empty, {}, "empty_file"),
        (unsupported, {}, "unsupported_format"),
        (wrong_pdf, {"format": "pdf"}, "format_mismatch"),
        (wrong_html, {}, "format_mismatch"),
        (oversized, {}, "file_too_large"),
        (directory, {}, "not_regular_file"),
    ]
    documents = [
        request(path, f"candidate-{i}", **fields) for i, (path, fields, _) in enumerate(candidates)
    ]
    result = gateway(*(approval(document) for document in documents), max_bytes=4096).run(
        spec(*documents)
    )
    assert [item["code"] for item in result.report["items"]] == [row[2] for row in candidates]
    assert result.report["summary"]["failed"] == len(candidates)
    assert all(item["event_id"] is None for item in result.report["items"])
    assert not state.exists()


def test_symlink_cannot_point_even_inside_approved_root(intake):
    inbox, state, gateway = intake
    target = inbox / "target.html"
    target.write_bytes(HTML)
    link = inbox / "alias.html"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks requires OS support and permission")
    document = request(link)
    result = gateway(approval(document)).run(spec(document))
    assert result.report["items"][0]["code"] == "path_link_disallowed"
    assert not state.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_windows_junction_cannot_point_even_inside_approved_root(intake):
    inbox, state, gateway = intake
    target = inbox / "target folder"
    target.mkdir()
    (target / "document.html").write_bytes(HTML)
    junction = inbox / "junction alias"
    process = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        check=False,
    )
    if process.returncode:
        pytest.skip("Filesystem does not support creating a directory junction")
    try:
        document = request(junction / "document.html")
        result = gateway(approval(document)).run(spec(document))
        assert result.report["items"][0]["code"] == "path_link_disallowed"
        assert not state.exists()
    finally:
        junction.rmdir()


@pytest.mark.parametrize("behavior", ["partial_read", "file_changed"])
def test_short_read_or_file_change_is_never_committed(intake, monkeypatch, behavior):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    document = request(path)
    open_source = _intake_files.open_local_binary

    class SourceProxy:
        def __init__(self, stream):
            self.stream = stream
            self.bytes_read = False

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            if behavior == "partial_read":
                return b""
            if not self.bytes_read:
                self.bytes_read = True
                original_stat = self.stream.fileno()
                stat = os.fstat(original_stat)
                future_mtime = stat.st_mtime_ns + 2_000_000_000
                if os.name == "nt":
                    # Simulate the post-read observation while Windows keeps
                    # the actual input handle protected against writers.
                    fstat = os.fstat

                    def changed_fstat(fd):
                        data = fstat(fd)
                        if fd != original_stat:
                            return data
                        return SimpleNamespace(
                            st_dev=data.st_dev,
                            st_ino=data.st_ino,
                            st_size=data.st_size,
                            st_mtime_ns=future_mtime,
                            st_ctime_ns=data.st_ctime_ns,
                        )

                    monkeypatch.setattr(_intake_files.os, "fstat", changed_fstat)
                else:
                    os.utime(path, ns=(stat.st_atime_ns, future_mtime))
            return self.stream.read(size)

    @contextmanager
    def intercepted(path):
        with open_source(path) as stream:
            yield SourceProxy(stream)

    monkeypatch.setattr(_intake_files, "open_local_binary", intercepted)
    result = gateway(approval(document)).run(spec(document))
    item = result.report["items"][0]
    assert item["code"] == behavior and item["event_id"] is None
    assert not state.exists()


def test_trusted_digest_is_required_even_if_spec_omits_it(intake):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    document = request(path)
    result = gateway(approval(document, expected_sha256="0" * 64)).run(spec(document))
    assert result.report["items"][0]["code"] == "checksum_mismatch"
    assert not state.exists()


def test_authorization_expiring_during_snapshot_prevents_store(intake, monkeypatch):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    document = request(path)
    original_snapshot = internal_import.snapshot_document
    before = datetime(2098, 1, 1, tzinfo=UTC)
    expires_at = datetime(2099, 1, 1, tzinfo=UTC)
    clock = before

    class IntakeClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock

    @contextmanager
    def advance_clock(*args, **kwargs):
        nonlocal clock
        with original_snapshot(*args, **kwargs) as opened:
            clock = expires_at
            yield opened

    monkeypatch.setattr(internal_import, "datetime", IntakeClock)
    monkeypatch.setattr(internal_import, "snapshot_document", advance_clock)
    result = gateway(approval(document, expires_at=expires_at.isoformat())).run(spec(document))
    assert result.report["items"][0]["code"] == "authorization_expired"
    assert not state.exists()


def test_changes_to_operating_file_after_snapshot_do_not_change_import(intake, monkeypatch):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    document = request(path)
    original_snapshot = internal_import.snapshot_document
    replacement = b"<p>Synthetic replacement after snapshot</p>"

    @contextmanager
    def replace_source(*args, **kwargs):
        with original_snapshot(*args, **kwargs) as opened:
            path.write_bytes(replacement)
            yield opened

    monkeypatch.setattr(internal_import, "snapshot_document", replace_source)
    result = gateway(approval(document)).run(spec(document))
    item = result.report["items"][0]
    assert item["status"] == "exported" and result.verification.valid
    assert (state / "originals" / item["sha256"]).read_bytes() == HTML
    assert path.read_bytes() == replacement


def test_checksum_of_exact_bytes_at_storage_is_enforced(intake, monkeypatch):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    document = request(path)
    original_snapshot = internal_import.snapshot_document

    @contextmanager
    def corrupt_snapshot(*args, **kwargs):
        with original_snapshot(*args, **kwargs) as (stream, checksum):
            data = stream.read().replace(b"Synthetic", b"Alternate")
            yield BytesIO(data), checksum

    monkeypatch.setattr(internal_import, "snapshot_document", corrupt_snapshot)
    result = gateway(approval(document)).run(spec(document))
    item = result.report["items"][0]
    assert item["code"] == "storage_error" and item["event_id"] is None
    assert not list((state / "originals").glob("*"))
    assert not list((state / "provenance").glob("*"))


def test_export_failure_preserves_originals_and_item_accounting(intake, monkeypatch):
    inbox, state, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    documents = [request(path, "first"), request(path, "second")]

    def refuse_export(*args, **kwargs):
        raise ExportError("batch_write_error")

    monkeypatch.setattr(internal_import, "export_batch", refuse_export)
    result = gateway(*(approval(doc) for doc in documents)).run(spec(*documents))
    assert result.manifest_path is None
    assert result.report["batch_error"] == "batch_write_error"
    assert result.report["summary"]["failed"] == result.report["summary"]["total"] == 2
    for index, item in enumerate(result.report["items"]):
        assert item["input_index"] == index and item["code"] == "batch_write_error"
        assert item["event_id"] and item["export_input_index"] is None
        assert (state / "originals" / item["sha256"]).read_bytes() == HTML


def test_omitted_export_record_still_links_its_report_item_and_event(intake, monkeypatch):
    inbox, _, gateway = intake
    path = inbox / "synthetic.html"
    path.write_bytes(HTML)
    first = request(path, "first")
    second = request(path, "second")
    publish = export._publish

    def refuse_first_record(target, payload):
        if target.parent.name == "records" and target.name == "0.json":
            raise OSError("synthetic write failure")
        publish(target, payload)

    monkeypatch.setattr(export, "_publish", refuse_first_record)
    result = gateway(approval(first), approval(second)).run(spec(first, second))
    failed, exported = result.report["items"]
    assert result.report["batch_error"] is None and result.verification.valid
    assert failed["status"] == "failed" and failed["code"] == "record_write_error"
    assert exported["status"] == "exported"
    manifest = read_json(result.manifest_path)
    omission = manifest["omissions"][0]
    assert failed["event_id"] == omission["event_id"]
    assert failed["export_input_index"] == omission["input_index"] == 0
    assert exported["export_input_index"] == manifest["records"][0]["input_index"] == 1


def test_operating_paths_embedded_values_and_parser_diagnostics_do_not_leak(
    intake, caplog, capsys, monkeypatch, pdf_bytes
):
    inbox, state, gateway = intake
    private_path = inbox / "private-filename-fixture.pdf"
    private_text = "PRIVATE_PDF_TEXT_FIXTURE"
    private_diagnostic = "RAW_PARSER_DIAGNOSTIC_FIXTURE"
    private_request_value = "REJECTED_REQUEST_VALUE_FIXTURE"
    private_path.write_bytes(pdf_bytes([[(72, 720, private_text)]]))
    document = request(private_path, format="pdf")
    forbidden_doc = request(
        private_path, "invalid", locator=f"https://fixture.invalid/{private_request_value}"
    )
    original_extract = PDFExtractor.extract

    def emit_parser_diagnostic(*args, **kwargs):
        logging.getLogger("pypdf._page").warning(private_diagnostic)
        return original_extract(*args, **kwargs)

    monkeypatch.setattr(PDFExtractor, "extract", emit_parser_diagnostic)
    result = gateway(approval(document)).run(spec(forbidden_doc, document))
    assert result.report["items"][0]["code"] == "invalid_document_spec"
    assert result.report["items"][1]["status"] == "exported"
    assert result.verification.valid
    captures = capsys.readouterr()
    report_and_logs = json.dumps(result.report) + captures.out + captures.err + caplog.text
    event = next((state / "provenance").glob("*.json")).read_text(encoding="utf-8")
    manifest = result.manifest_path.read_text(encoding="utf-8")
    for value in (
        str(private_path),
        private_path.name,
        private_text,
        private_diagnostic,
        private_request_value,
    ):
        assert value not in report_and_logs + event + manifest


def test_embedded_html_references_do_not_run_or_access_network(intake, monkeypatch):
    inbox, _, gateway = intake
    path = inbox / "linked.html"
    path.write_bytes(
        b"<html><head><link rel='stylesheet' href='https://fixture.invalid/style.css'></head>"
        b"<body><p>Synthetic text</p><script src='https://fixture.invalid/fixture.js'>"
        b"NEVER_EXECUTE_ME</script></body></html>"
    )
    document = request(path)

    def blocked(*args, **kwargs):
        pytest.fail("Internal intake attempted DNS or network access")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    result = gateway(approval(document)).run(spec(document))
    assert result.verification.valid
    record = read_json(result.manifest_path.parent / "records" / "0.json")
    assert [block["text"] for block in record["content"]] == ["Synthetic text"]


def test_valid_original_with_failed_text_extraction_is_traced_without_success(
    intake, image_only_pdf
):
    inbox, state, gateway = intake
    path = inbox / "scan.pdf"
    path.write_bytes(image_only_pdf)
    document = request(path, format="pdf")
    result = gateway(approval(document)).run(spec(document))
    item = result.report["items"][0]
    assert item["status"] == "failed"
    assert (
        item["event_id"] and (state / "originals" / item["sha256"]).read_bytes() == image_only_pdf
    )
    assert result.verification.valid
    manifest = read_json(result.manifest_path)
    record = read_json(
        result.manifest_path.parent / manifest["records"][item["export_input_index"]]["record_path"]
    )
    validate_record(record)
    assert record["content"] == [] and record["extraction"]["status"] == "failed"


def test_configured_reuse_status_needs_an_explicit_grant(intake):
    inbox, _, gateway = intake
    path = inbox / "restricted.html"
    path.write_bytes(HTML)
    document = request(path, reuse="restricted")
    result = gateway(approval(document)).run(spec(document))
    assert result.verification.valid
    record = read_json(result.manifest_path.parent / "records" / "0.json")
    validate_record(record)
    assert record["rights"]["reuse"] == "restricted"
    assert record["rights"]["evidence"]


def test_cli_requires_separate_approvals_and_handles_mixed_results(intake, tmp_path, capsys):
    inbox, state, _ = intake
    operating_file = inbox / "private-input-fixture.html"
    operating_file.write_bytes(HTML)
    authorization_path = tmp_path / "operator-approvals.json"
    spec_path = tmp_path / "submitted-spec.json"
    document = request(operating_file)
    denied = request(operating_file, "no-grant")
    authorization_path.write_text(json.dumps(approvals(approval(document))), encoding="utf-8")
    spec_path.write_text(json.dumps(spec(document, denied)), encoding="utf-8")
    args = ["--spec", str(spec_path), "--intake-root", str(inbox), "--state-root", str(state)]

    assert intake_cli(args) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err) == {"error": "invalid_arguments"}
    assert not state.exists()

    args += ["--trusted-approvals", str(authorization_path)]
    assert intake_cli([*args, "--dry-run"]) == 1
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["summary"]["validated"] == dry_run["summary"]["failed"] == 1
    assert not state.exists()

    assert intake_cli(args) == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert captured.err == ""
    assert report["summary"]["exported"] == report["summary"]["failed"] == 1
    assert operating_file.name not in captured.out


def test_cli_rejects_duplicate_json_keys_without_echoing_values(intake, tmp_path, capsys):
    inbox, state, _ = intake
    authorization_path = tmp_path / "operator-approvals.json"
    spec_path = tmp_path / "submitted-spec.json"
    approval_json = (
        '{"authorization_version":"0.1","authorizations":[],"authorizations":["PRIVATE"]}'
    )
    authorization_path.write_text(approval_json, encoding="utf-8")
    spec_path.write_text(json.dumps(spec()), encoding="utf-8")
    code = intake_cli(
        [
            "--spec",
            str(spec_path),
            "--trusted-approvals",
            str(authorization_path),
            "--intake-root",
            str(inbox),
            "--state-root",
            str(state),
        ]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {"error": "trusted_approvals_read_error"}
    assert not state.exists()
