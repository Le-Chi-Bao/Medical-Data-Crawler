"""Synthetic, network-blocked public intake and rights regression tests."""

import copy
import hashlib
import json

import pytest

from medical_data_crawler.contract import validate_record
from medical_data_crawler.curated import CuratedPublicDocumentImporter, verify_report
from medical_data_crawler.curated_cli import inventory, main
from medical_data_crawler.curated_manifest import (
    CuratedError,
    digest,
    read_json,
    validate_approvals,
    validate_manifest,
)

VI_TEXT = "Tài liệu tổng hợp: tổn thương da, nốt ruồi, chẩn đoán phân biệt."
HTML = (
    '<!doctype html><html lang="vi"><meta charset="utf-8"><title>Mẫu</title>'
    f"<body><article><h1>Hình thái</h1><p>{VI_TEXT}</p></article></body></html>"
).encode()


def document(path, data, *, key="vn-test", operations=None, origin="synthetic"):
    return {
        "document_id": key,
        "title": "Tài liệu tổng hợp",
        "publisher": "Synthetic publisher",
        "original_publisher": "Synthetic publisher",
        "source_url": "https://example.org/" + key,
        "download_url": None,
        "language": "vi",
        "published_on": None,
        "format": path.suffix[1:],
        "category": "medical_reference_websites",
        "scope": ["K01"],
        "scope_evidence": "Synthetic heading Hình thái",
        "local_path": str(path),
        "expected_sha256": hashlib.sha256(data).hexdigest(),
        "submitted_at": "2026-11-26T00:00:00Z",
        "data_origin": origin,
        "source_status": "verified",
        "verified_at": "2026-11-26T00:00:00Z",
        "access_status": "public_read",
        "review_notes": "Synthetic test only",
        "rights": {
            "status": "reviewed",
            "license_uri": None,
            "evidence_url": None,
            "evidence_note": "Synthetic fixture owned by tests",
            "allowed_operations": operations
            if operations is not None
            else ["read", "store", "extract"],
        },
    }


def grant(doc, **changes):
    result = {
        "document_id": doc["document_id"],
        "manifest_entry_sha256": digest(doc),
        "expected_sha256": doc["expected_sha256"],
        "allowed_operations": list(doc["rights"]["allowed_operations"]),
        "reviewer": "synthetic-reviewer",
        "evidence": "Synthetic test fixture",
        "expires_at": "2099-01-01T00:00:00Z",
        "active": True,
    }
    result.update(changes)
    return result


def envelope(docs):
    return {"curated_manifest_version": "0.1", "documents": docs}


def approvals(grants):
    return {"curated_approval_version": "0.1", "approvals": grants}


def importer(tmp_path, docs, grants=None):
    return CuratedPublicDocumentImporter(
        intake_root=tmp_path,
        state_root=tmp_path / "state",
        approvals=approvals([grant(d) for d in docs] if grants is None else grants),
    )


def report_path(tmp_path, report):
    return tmp_path / "state" / "reports" / report["run_id"] / "report.json"


def test_unicode_html_provenance_export_and_duplicate(tmp_path):
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML)
    runner = importer(tmp_path, [doc])
    reports = [runner.run(envelope([doc])) for _ in range(2)]
    assert len(list((tmp_path / "state/originals").iterdir())) == 1
    assert reports[1]["items"][0]["duplicate"] is True
    assert (
        reports[0]["items"][0]["record_document_id"] == reports[1]["items"][0]["record_document_id"]
    )
    assert reports[0]["items"][0]["event_id"] != reports[1]["items"][0]["event_id"]
    for report in reports:
        assert report["batch_error"] is None
        assert report["summary"]["real_original_documents_imported"] == 0
        assert report["summary"]["synthetic_documents"] == 1
        item = report["items"][0]
        assert VI_TEXT in (tmp_path / "state" / item["text_path"]).read_text(encoding="utf-8")
        manifest_path = tmp_path / "state" / report["export_manifest"]
        batch = read_json(manifest_path)
        record = read_json(manifest_path.parent / batch["records"][0]["record_path"])
        validate_record(record)
        assert record["source"]["source_id"] == "curated-public"
        assert record["source"]["locator"] == doc["source_url"]
        assert record["metadata"]["language"] == "vi"
        assert record["scope"] == ["K01"]
        assert record["rights"]["reuse"] == "unknown"
        event = read_json(tmp_path / "state/provenance" / (item["event_id"] + ".json"))
        assert "internal" not in event
        assert event["curated_public"]["manifest_entry_sha256"] == digest(doc)
        assert (
            verify_report(report_path(tmp_path, report), tmp_path / "state")["integrity"]
            == "verified"
        )
    assert path.read_bytes() == HTML


@pytest.mark.parametrize("preview", [False, True])
def test_dry_run_and_preview_leave_no_state(tmp_path, preview):
    path = tmp_path / "a.htm"
    path.write_bytes(HTML)
    doc = document(path, HTML)
    report = importer(tmp_path, [doc]).run(envelope([doc]), dry_run=not preview, preview=preview)
    assert not (tmp_path / "state").exists()
    assert report["items"][0]["status"] == ("previewed" if preview else "validated")
    if preview:
        assert VI_TEXT in report["items"][0]["preview_text"]


@pytest.mark.parametrize(
    ("operations", "status", "code"),
    [
        ([], "blocked", "read_not_authorized"),
        (["read"], "blocked", "store_not_authorized"),
        (["read", "store"], "stored_only", "extract_not_authorized"),
    ],
)
def test_operation_gates_before_extract(tmp_path, monkeypatch, operations, status, code):
    def forbidden(*args, **kwargs):
        raise AssertionError("Extractor must not run")

    monkeypatch.setattr("medical_data_crawler.html_extraction.HTMLExtractor.extract", forbidden)
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML, operations=operations)
    report = importer(tmp_path, [doc]).run(envelope([doc]))
    item = report["items"][0]
    assert (item["status"], item["code"]) == (status, code)
    assert item["text_path"] is None and not item["rag_eligible"]
    assert bool(item["event_id"]) == (status == "stored_only")
    assert (
        verify_report(report_path(tmp_path, report), tmp_path / "state")["integrity"] == "verified"
    )


@pytest.mark.parametrize(
    "condition", ["missing", "expired", "inactive", "binding", "grant_store", "grant_extract"]
)
def test_separate_trusted_approval(tmp_path, condition):
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML)
    g = grant(doc)
    if condition == "expired":
        g["expires_at"] = "2000-01-01T00:00:00Z"
    elif condition == "inactive":
        g["active"] = False
    elif condition == "binding":
        doc["publisher"] = "Modified metadata"
    elif condition == "grant_store":
        g["allowed_operations"].remove("store")
    elif condition == "grant_extract":
        g["allowed_operations"].remove("extract")
    report = importer(tmp_path, [doc], [] if condition == "missing" else [g]).run(envelope([doc]))
    item = report["items"][0]
    assert item["status"] == ("stored_only" if condition == "grant_extract" else "blocked")
    assert item["text_path"] is None


@pytest.mark.parametrize(
    ("ops", "origin", "eligible"),
    [
        (["read", "store", "extract"], "real", False),
        (["read", "store", "extract", "rag"], "real", False),
        (["read", "store", "extract", "reuse", "rag"], "real", True),
        (["read", "store", "extract", "reuse", "rag"], "synthetic", False),
    ],
)
def test_rag_requires_quality_reuse_and_explicit_purpose(tmp_path, ops, origin, eligible):
    # Origin=real exercises the accounting branch using synthetic bytes only.
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML, operations=ops, origin=origin)
    report = importer(tmp_path, [doc]).run(envelope([doc]))
    assert report["items"][0]["rag_eligible"] is eligible
    assert report["summary"]["rag_eligible"] == int(eligible)


def test_missing_license_stays_unknown_and_pending_never_reads_file(tmp_path):
    path = tmp_path / "missing.html"
    doc = document(path, HTML)
    doc["rights"].update(status="pending_review", allowed_operations=[], evidence_note=None)
    report = importer(tmp_path, [doc], []).run(envelope([doc]))
    assert report["items"][0]["code"] == "rights_not_reviewed"
    assert report["summary"]["pending_rights"] == 1
    assert not (tmp_path / "state/originals").exists()


@pytest.mark.parametrize("kind", ["missing", "corrupted", "checksum", "too_large", "outside"])
def test_file_failures_isolated_from_good_document(tmp_path, kind):
    path = tmp_path / ("bad.pdf" if kind == "corrupted" else "bad.html")
    data = b"%PDF-broken" if kind == "corrupted" else HTML
    if kind != "missing":
        path.write_bytes(data)
    bad = document(path, data, key="bad")
    good_path = tmp_path / "good.html"
    good_path.write_bytes(HTML)
    good = document(good_path, HTML, key="good")
    if kind == "checksum":
        bad["expected_sha256"] = "0" * 64
    elif kind == "too_large":
        path.write_bytes(HTML + b" " * 2048)
    elif kind == "outside":
        bad["local_path"] = str(tmp_path.parent / "outside.html")
    runner = importer(tmp_path, [bad, good])
    runner.max_bytes = 1024
    report = runner.run(envelope([bad, good]))
    assert report["items"][0]["status"] == "blocked"
    assert report["items"][1]["status"] == "extracted"
    assert report["batch_error"] is None
    assert (
        verify_report(report_path(tmp_path, report), tmp_path / "state")["integrity"] == "verified"
    )


def test_pdf_text_pages_and_scan_ocr(tmp_path, pdf_bytes, image_only_pdf):
    docs = []
    for key, data in [
        ("text", pdf_bytes([[(72, 720, "Synthetic PDF text")]])),
        ("scan", image_only_pdf),
    ]:
        path = tmp_path / (key + ".pdf")
        path.write_bytes(data)
        docs.append(document(path, data, key=key))
    report = importer(tmp_path, docs).run(envelope(docs))
    first, second = report["items"]
    assert first["extraction_status"] == "success"
    assert first["pages"][0]["page_number"] == 1
    assert second["extraction_status"] == "failed"
    assert second["code"] == "OCR_REQUIRED"
    assert report["summary"]["ocr_required"] == 1
    assert report["batch_error"] is None
    assert (
        verify_report(report_path(tmp_path, report), tmp_path / "state")["integrity"] == "verified"
    )


def test_vietnamese_pdf_unicode_cmap(tmp_path):
    """Embedded synthetic Unicode map, no system fonts or external files."""
    from io import BytesIO

    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    cmap = DecodedStreamObject()
    mappings = "\n".join(f"<{i:04X}> <{ord(c):04X}>" for i, c in enumerate(VI_TEXT, 1))
    cmap.set_data(
        (
            "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            "/CIDSystemInfo << /Registry (Test) /Ordering (Unicode) /Supplement 0 >> def\n"
            "/CMapName /TestUnicode def /CMapType 2 def\n"
            "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            f"{len(VI_TEXT)} beginbfchar\n{mappings}\nendbfchar\n"
            "endcmap CMapName currentdict /CMap defineresource pop end end"
        ).encode()
    )
    descendant = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType2"),
            NameObject("/BaseFont"): NameObject("/Synthetic"),
        }
    )
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject("/Synthetic"),
            NameObject("/Encoding"): NameObject("/Identity-H"),
            NameObject("/DescendantFonts"): ArrayObject([descendant]),
            NameObject("/ToUnicode"): writer._add_object(cmap),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    content = DecodedStreamObject()
    encoded = "".join(f"{i:04X}" for i in range(1, len(VI_TEXT) + 1))
    content.set_data(f"BT /F1 12 Tf 72 720 Td <{encoded}> Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    path = tmp_path / "unicode.pdf"
    path.write_bytes(output.getvalue())
    doc = document(path, output.getvalue())
    report = importer(tmp_path, [doc]).run(envelope([doc]))
    item = report["items"][0]
    assert item["extraction_status"] == "success"
    assert VI_TEXT in (tmp_path / "state" / item["text_path"]).read_text(encoding="utf-8")


@pytest.mark.parametrize("part", ["original", "text", "record", "event", "page", "quality", "rag"])
def test_tamper_detected(tmp_path, pdf_bytes, part):
    data = pdf_bytes([[(72, 720, "Synthetic PDF")]])
    path = tmp_path / "a.pdf"
    path.write_bytes(data)
    doc = document(path, data)
    report = importer(tmp_path, [doc]).run(envelope([doc]))
    item = report["items"][0]
    root = tmp_path / "state"
    if part == "original":
        (root / "originals" / item["sha256"]).write_bytes(b"changed")
    elif part == "text":
        (root / item["text_path"]).write_text("changed", encoding="utf-8")
    elif part == "event":
        event_path = root / "provenance" / (item["event_id"] + ".json")
        event = read_json(event_path)
        event["curated_public"]["approval_sha256"] = "0" * 64
        event_path.write_text(json.dumps(event), encoding="utf-8")
    elif part == "record":
        batch = read_json(root / report["export_manifest"])
        (root / report["export_manifest"]).parent.joinpath(
            batch["records"][0]["record_path"]
        ).write_text("{}")
    elif part == "page":
        report["items"][0]["pages"][0]["page_number"] = 9
        report_path(tmp_path, report).write_text(json.dumps(report), encoding="utf-8")
    elif part == "quality":
        sidecar = root / item["quality_path"]
        quality = read_json(sidecar)
        quality["result"]["ocr_required"] = True
        sidecar.write_text(json.dumps(quality), encoding="utf-8")
    else:
        report["items"][0]["rag_eligible"] = True
        report_path(tmp_path, report).write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(CuratedError):
        verify_report(report_path(tmp_path, report), root)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format", "exe"),
        ("scope", ["K09"]),
        ("scope_evidence", None),
        ("language", ""),
        ("published_on", "2026-02-30"),
        ("source_url", "file:///local"),
        ("expected_sha256", "bad"),
        ("submitted_at", "2026-11-26"),
        ("title", 10),
    ],
)
def test_invalid_metadata(tmp_path, field, value):
    doc = document(tmp_path / "a.html", HTML)
    doc[field] = value
    with pytest.raises(CuratedError):
        validate_manifest(envelope([doc]))


def test_duplicate_ids_and_no_rights_without_evidence(tmp_path):
    doc = document(tmp_path / "a.html", HTML)
    with pytest.raises(CuratedError, match="duplicate_document_id"):
        validate_manifest(envelope([doc, copy.deepcopy(doc)]))
    doc["rights"]["evidence_note"] = None
    with pytest.raises(CuratedError, match="rights_evidence_missing"):
        validate_manifest(envelope([doc]))
    with pytest.raises(CuratedError):
        validate_approvals(approvals([{}]))


def test_cli_create_validate_inventory_and_existing_file_preserved(tmp_path, capsys):
    doc = document(tmp_path / "a.html", HTML)
    doc["rights"].update(status="pending_review", allowed_operations=[])
    source = tmp_path / "candidates.json"
    target = tmp_path / "sources.json"
    source.write_text(json.dumps(envelope([doc])), encoding="utf-8")
    assert main(["create", "--from-candidates", str(source), "--output", str(target)]) == 0
    assert read_json(target) == read_json(source)
    assert main(["create", "--from-candidates", str(source), "--output", str(target)]) == 2
    for command in ("validate", "check-files", "fingerprints", "candidates", "report"):
        assert main([command, "--manifest", str(target)]) == 0
    assert inventory(envelope([doc]))["summary"]["real_original_documents_imported"] == 0
    assert "Tài liệu" in capsys.readouterr().out


def test_cli_import_verify_inspect_and_current_revocation(tmp_path, capsys):
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML)
    spec, approval = tmp_path / "sources.json", tmp_path / "operator.json"
    spec.write_text(json.dumps(envelope([doc])), encoding="utf-8")
    approval.write_text(json.dumps(approvals([grant(doc)])), encoding="utf-8")
    args = [
        "--manifest",
        str(spec),
        "--trusted-approvals",
        str(approval),
        "--intake-root",
        str(tmp_path),
        "--state-root",
        str(tmp_path / "state"),
    ]
    assert main(["import", *args, "--dry-run"]) == 0
    assert main(["preview", *args]) == 0
    assert main(["import", *args]) == 0
    rp = next((tmp_path / "state/reports").glob("*/report.json"))
    assert main(["verify", "--report", str(rp), "--state-root", str(tmp_path / "state")]) == 0
    inspect_args = [
        "inspect-text",
        "--report",
        str(rp),
        "--document-id",
        doc["document_id"],
        "--trusted-approvals",
        str(approval),
        "--state-root",
        str(tmp_path / "state"),
    ]
    assert main(inspect_args) == 0
    assert VI_TEXT in capsys.readouterr().out
    approval.write_text(json.dumps(approvals([grant(doc, active=False)])), encoding="utf-8")
    assert main(inspect_args) == 2


def test_disabled_approval_template_does_not_grant_rights(tmp_path):
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML)
    spec, output = tmp_path / "sources.json", tmp_path / "approval-template.json"
    spec.write_text(json.dumps(envelope([doc])), encoding="utf-8")
    assert main(["approval-template", "--manifest", str(spec), "--output", str(output)]) == 0
    template = read_json(output)
    g = validate_approvals(template)[doc["document_id"]]
    assert g["active"] is False and g["allowed_operations"] == []
    runner = CuratedPublicDocumentImporter(
        intake_root=tmp_path, state_root=tmp_path / "state", approvals=template
    )
    assert runner.run(envelope([doc]))["items"][0]["status"] == "blocked"


def test_relative_path_unknown_scope_and_unknown_metadata(tmp_path):
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML)
    doc.update(local_path="a.html", scope=[], scope_evidence=None, original_publisher=None)
    runner = CuratedPublicDocumentImporter(
        intake_root=tmp_path,
        state_root=tmp_path / "state",
        base_dir=tmp_path,
        approvals=approvals([grant(doc)]),
    )
    report = runner.run(envelope([doc]))
    manifest_path = tmp_path / "state" / report["export_manifest"]
    batch = read_json(manifest_path)
    record = read_json(manifest_path.parent / batch["records"][0]["record_path"])
    assert record["scope"] == "unknown" and record["scope_evidence"] is None
    assert record["metadata"]["published_on"] is None
    assert report["manifest"]["documents"][0]["original_publisher"] is None


def test_license_link_without_grant_is_not_approval(tmp_path):
    path = tmp_path / "a.html"
    path.write_bytes(HTML)
    doc = document(path, HTML)
    doc["rights"]["license_uri"] = "https://creativecommons.org/licenses/by/4.0/"
    report = importer(tmp_path, [doc], []).run(envelope([doc]))
    assert report["items"][0]["code"] == "approval_missing_or_inactive"


def test_suspicious_unicode_never_rag_eligible(tmp_path):
    data = HTML.replace(VI_TEXT.encode(), "Lỗi kí tự \ufffd".encode())
    path = tmp_path / "a.html"
    path.write_bytes(data)
    doc = document(
        path, data, origin="real", operations=["read", "store", "extract", "reuse", "rag"]
    )
    report = importer(tmp_path, [doc]).run(envelope([doc]))
    assert not report["items"][0]["rag_eligible"]
    assert "suspicious_unicode_manual_review" in report["items"][0]["warnings"]


def test_raw_json_size_and_duplicate_keys(tmp_path):
    path = tmp_path / "a.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(CuratedError, match="duplicate_json_key"):
        read_json(path)
    path.write_bytes(b" " * (1024 * 1024 + 1))
    with pytest.raises(CuratedError, match="json_size_limit"):
        read_json(path)


def test_large_derived_record_is_not_limited_like_intake_metadata(tmp_path):
    # Source manifests stay small; extracted text records can exceed one MiB.
    data = HTML.replace(VI_TEXT.encode(), (VI_TEXT * 20000).encode())
    path = tmp_path / "large.html"
    path.write_bytes(data)
    doc = document(path, data)
    report = importer(tmp_path, [doc]).run(envelope([doc]))
    assert report["batch_error"] is None
    assert report["items"][0]["status"] == "extracted"
    assert (
        verify_report(report_path(tmp_path, report), tmp_path / "state")["integrity"] == "verified"
    )
