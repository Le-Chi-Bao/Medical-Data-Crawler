"""Curated public documents: bounded local intake, existing v0.1 export, no network."""

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ._intake_files import (
    INTAKE_MEDIA_TYPES,
    MAX_INPUT_BYTES,
    IntakeFileError,
    check_local_path,
    private_pdf_diagnostics,
    snapshot_document,
)
from .acquisition import AcquisitionResult, DocumentRequest
from .contract import validate_record
from .curated_manifest import (
    CuratedError,
    authorize,
    digest,
    read_json,
    timestamp,
    validate_approvals,
    validate_manifest,
)
from .export import ExportError, _publish, export_batch, verify_batch
from .html_extraction import HTMLExtractor
from .pdf_extraction import PDFExtractor
from .pipeline import OfflinePipeline, RecordRights
from .provenance import CuratedPublicTrace, ProvenanceStore, document_id
from .storage import ArtifactStore

SOURCE_ID = "curated-public"
QUALITY_FIELDS = (
    "document_id",
    "data_origin",
    "sha256",
    "event_id",
    "extraction_status",
    "rag_eligible",
    "ocr_required",
    "warnings",
    "text_path",
    "text_sha256",
    "pages",
)


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    _publish(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _quality(extracted):
    text = "\n\n".join(block.text for block in extracted.blocks)
    warnings = list(extracted.warnings)
    ocr = extracted.document_type == "pdf" and any(p.status == "no_text" for p in extracted.pages)
    suspicious = any(marker in text for marker in ("\ufffd", "Ã¡", "Ã´", "á»", "áº", "\x00"))
    if ocr:
        warnings.append("OCR_REQUIRED")
    if suspicious:
        warnings.append("suspicious_unicode_manual_review")
    if not text.strip():
        warnings.append("blank_text")
    # Conservative automatic gate. Partial layout/text requires human fidelity review.
    adequate = bool(text.strip()) and extracted.status == "success" and not suspicious and not ocr
    return text, adequate, ocr, warnings


class CuratedPublicDocumentImporter:
    """Operator grants are separate trusted input, following the internal intake trust model."""

    def __init__(
        self,
        *,
        intake_root: Path,
        state_root: Path,
        approvals=None,
        base_dir: Path | None = None,
        max_bytes=MAX_INPUT_BYTES,
    ):
        self.intake_root = check_local_path(Path(intake_root).absolute())
        self.state_root = check_local_path(Path(state_root).absolute())
        self.base_dir = Path(base_dir or Path.cwd()).absolute()
        self.grants = validate_approvals(
            approvals or {"curated_approval_version": "0.1", "approvals": []}
        )
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_INPUT_BYTES:
            raise CuratedError("invalid_size_limit")
        self.max_bytes = max_bytes

    def _path(self, doc):
        if not doc["local_path"]:
            raise CuratedError("local_file_not_declared")
        path = Path(doc["local_path"])
        # Do not resolve: snapshot_document must see and reject links and traversal.
        return path if path.is_absolute() else self.base_dir / path

    def run(self, manifest, *, dry_run=False, preview=False):
        documents = validate_manifest(manifest)
        items, results = [], []
        artifacts = provenance = None
        run_id = uuid4().hex
        run_dir = self.state_root / "reports" / run_id
        for doc in documents:
            item = {
                "document_id": doc["document_id"],
                "record_document_id": document_id(SOURCE_ID, doc["document_id"]),
                "data_origin": doc["data_origin"],
                "status": "blocked",
                "code": None,
                "sha256": None,
                "event_id": None,
                "extraction_status": None,
                "rag_eligible": False,
                "ocr_required": False,
                "duplicate": False,
                "warnings": [],
                "text_path": None,
                "text_sha256": None,
                "quality_path": None,
                "export_input_index": None,
                "pages": [],
                "missing_metadata": [
                    k for k in ("title", "publisher", "language", "published_on") if not doc[k]
                ],
            }
            items.append(item)
            try:
                operations = ["read", "store"] + (["extract"] if preview else [])
                grant = authorize(doc, self.grants, operations)
                can_extract = (
                    "extract" in doc["rights"]["allowed_operations"]
                    and "extract" in grant["allowed_operations"]
                )
                with snapshot_document(
                    str(self._path(doc)),
                    (self.intake_root,),
                    doc["format"],
                    self.max_bytes,
                    grant["expected_sha256"],
                    dry_run=dry_run or preview,
                ) as (stream, checksum):
                    authorize(doc, self.grants, operations)
                    item["sha256"] = checksum
                    if dry_run and not preview:
                        item["status"] = "validated"
                        if not can_extract:
                            item["code"] = "extract_not_authorized"
                        continue
                    if preview:
                        with private_pdf_diagnostics():
                            extractor = (
                                PDFExtractor() if doc["format"] == "pdf" else HTMLExtractor()
                            )
                            extracted = extractor.extract(stream)
                        authorize(doc, self.grants, ["read", "store", "extract"])
                    else:
                        if artifacts is None:
                            artifacts = ArtifactStore(
                                check_local_path(self.state_root / "originals")
                            )
                            provenance = ProvenanceStore(
                                check_local_path(self.state_root / "provenance"), artifacts
                            )
                        target = artifacts.root / checksum
                        item["duplicate"] = target.exists()
                        artifact = artifacts.put(stream, expected_sha256=checksum)
                        now = datetime.now(UTC)
                        event_id = provenance.record(
                            source_id=SOURCE_ID,
                            logical_key=doc["document_id"],
                            locator=doc["source_url"],
                            acquired_at=now,
                            checksum=checksum,
                            curated=CuratedPublicTrace("0.1", digest(doc), digest(grant)),
                        )
                        item["event_id"] = event_id
                        if not can_extract:
                            item["status"], item["code"] = "stored_only", "extract_not_authorized"
                            continue
                        authorize(doc, self.grants, ["read", "store", "extract"])
                        request = DocumentRequest(
                            None, SOURCE_ID, doc["document_id"], doc["source_url"]
                        )
                        acquired = AcquisitionResult(
                            request,
                            item["record_document_id"],
                            now,
                            INTAKE_MEDIA_TYPES[doc["format"]],
                            artifact,
                            event_id,
                            (),
                            frozenset({INTAKE_MEDIA_TYPES[doc["format"]]}),
                        )
                        rights = RecordRights(
                            "curated_public_review",
                            "unknown",
                            doc["rights"]["evidence_url"] or grant["evidence"],
                        )
                        with private_pdf_diagnostics():
                            result = OfflinePipeline(artifacts, None).process_acquired(
                                acquired, rights=rights, snapshot_dir=artifacts.root
                            )
                        if result.record is None:
                            raise CuratedError("record_build_failed")
                        extracted = result.extraction
                        record = result.record
                        for key in ("title", "language", "published_on"):
                            if doc[key] is not None:
                                record["metadata"][key] = doc[key]
                        # Missing scope evidence is never inferred by keywords.
                        if doc["scope"]:
                            record["scope"] = doc["scope"]
                            record["scope_evidence"] = doc["scope_evidence"]
                        validate_record(record)
                text, adequate, ocr, warnings = _quality(extracted)
                if item["duplicate"]:
                    warnings.append("duplicate_original")
                authorize(doc, self.grants, ["read", "store", "extract"])
                item.update(
                    extraction_status=extracted.status,
                    warnings=warnings,
                    ocr_required=ocr,
                    pages=[asdict(page) for page in extracted.pages],
                    status="previewed" if preview else "extracted",
                )
                if extracted.status == "failed":
                    item["status"] = "preview_failed" if preview else "extraction_failed"
                    item["code"] = "OCR_REQUIRED" if ocr else "extraction_failed"
                try:
                    authorize(doc, self.grants, ["read", "store", "extract", "reuse", "rag"])
                    item["rag_eligible"] = adequate and doc["data_origin"] == "real" and not preview
                except CuratedError:
                    item["warnings"].append("downstream_rag_not_authorized")
                if preview:
                    item["preview_text"] = text
                else:
                    text_path = Path("extracted") / run_id / (doc["document_id"] + ".txt")
                    target = check_local_path(self.state_root / text_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    _publish(target, text.encode("utf-8"))
                    item["text_path"] = text_path.as_posix()
                    item["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    quality = {
                        "curated_quality_version": "0.1",
                        "result": {k: item[k] for k in QUALITY_FIELDS},
                        "page_count": extracted.page_count,
                        "source_encoding": extracted.source_encoding,
                    }
                    quality_path = text_path.with_suffix(".quality.json")
                    _write_json(check_local_path(self.state_root / quality_path), quality)
                    item["quality_path"] = quality_path.as_posix()
                    record["extraction"]["warnings"] += [
                        "curated_quality_sha256:" + digest(quality)
                    ]
                    validate_record(record)
                    item["export_input_index"] = len(results)
                    results.append(replace(result, record=record))
            except (CuratedError, IntakeFileError) as error:
                item["status"] = "blocked"
                item["code"] = error.code
            except Exception:
                item["status"] = "blocked"
                item["code"] = "intake_failed"
        export = None
        batch_error = None
        if results:
            try:
                # Recheck all grants immediately before the publication point.
                for doc, item in zip(documents, items, strict=True):
                    if item["export_input_index"] is not None:
                        authorize(doc, self.grants, ["read", "store", "extract"])
                exported = export_batch(
                    results, check_local_path(self.state_root / "exports"), provenance
                )
                checked = verify_batch(exported, provenance)
                if not checked.valid:
                    raise CuratedError(checked.error_code)
                if checked.manifest["omissions"]:
                    raise CuratedError("export_contains_omissions")
                export = exported.relative_to(self.state_root).as_posix()
            except (CuratedError, ExportError, IntakeFileError) as error:
                batch_error = error.code
                for item in items:
                    item["rag_eligible"] = False
        report = {
            "curated_report_version": "0.1",
            "run_id": run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "mode": "preview" if preview else "dry_run" if dry_run else "import",
            "network_requests": 0,
            "manifest": manifest,
            "approvals": list(self.grants.values()),
            "items": items,
            "export_manifest": export,
            "batch_error": batch_error,
        }
        report["summary"] = summarize(report)
        if not dry_run and not preview:
            _write_json(check_local_path(run_dir / "report.json"), report)
            _publish(run_dir / "report.md", readable_report(report).encode("utf-8"))
        return report


def summarize(report):
    items = report["items"]
    real = [i for i in items if i["data_origin"] == "real"]
    return {
        "candidates": len(items),
        "real_candidates": len(real),
        "synthetic_documents": len(items) - len(real),
        "source_verified": sum(
            d["source_status"] == "verified" for d in report["manifest"]["documents"]
        ),
        "pending_rights": sum(
            d["rights"]["status"] == "pending_review" for d in report["manifest"]["documents"]
        ),
        "restricted_or_rejected": sum(
            d["rights"]["status"] in ("restricted", "rejected")
            for d in report["manifest"]["documents"]
        ),
        "real_original_documents_imported": sum(bool(i["event_id"]) for i in real),
        "unique_originals": len({i["sha256"] for i in items if i["event_id"]}),
        "real_text_documents": sum(
            i["status"] == "extracted" and i["extraction_status"] in ("success", "partial")
            for i in real
        ),
        "ocr_required": sum(i["ocr_required"] for i in items),
        "rag_eligible": sum(i["rag_eligible"] for i in real) if not report["batch_error"] else 0,
        "blocked_or_failed": sum(
            i["status"] == "blocked" or i["extraction_status"] == "failed" for i in items
        ),
    }


def readable_report(report):
    lines = [
        "# Báo cáo corpus tiếng Việt",
        "",
        f"Chế độ: {report['mode']}; network requests: 0.",
        "",
        "Số liệu chỉ phản ánh lần chạy này; không cộng các lần import trùng thành tài liệu mới.",
        "",
    ]
    lines += [f"- {key}: {value}" for key, value in report["summary"].items()]
    lines += ["", "| ID | Trạng thái | Trích xuất | RAG | Mã |", "|---|---|---|---|---|"]
    lines += [
        f"| {i['document_id']} | {i['status']} | {i['extraction_status']} "
        f"| {i['rag_eligible']} | {i['code']} |"
        for i in report["items"]
    ]
    lines += [
        "",
        "Eligibility phản ánh quyền và kỹ thuật lúc chạy; cần kiểm tra lại quyền trước downstream.",
        "Layout PDF cần review thủ công. Không kiểm chứng tính đúng đắn y khoa.",
    ]
    for item in report["items"]:
        if item.get("warnings") or item.get("missing_metadata"):
            lines += [
                "",
                f"{item['document_id']}: warnings={item.get('warnings', [])}; "
                f"missing_metadata={item.get('missing_metadata', [])}",
            ]
    return "\n".join(lines) + "\n"


def verify_report(report_path: Path, state_root: Path):
    """Check history, artifacts (including store-only), text and v0.1 references offline."""
    report = read_json(report_path, max_bytes=128 * 1024 * 1024)
    try:
        if report["curated_report_version"] != "0.1" or report["mode"] != "import":
            raise CuratedError("invalid_report")
        docs = validate_manifest(report["manifest"])
        grants = validate_approvals(
            {"curated_approval_version": "0.1", "approvals": report["approvals"]}
        )
        artifacts = ArtifactStore(check_local_path(state_root.absolute() / "originals"))
        provenance = ProvenanceStore(
            check_local_path(state_root.absolute() / "provenance"), artifacts
        )
        batch = None
        if report["export_manifest"]:
            path = _report_path(state_root, report["export_manifest"])
            checked = verify_batch(path, provenance)
            if not checked.valid:
                raise CuratedError(checked.error_code)
            batch = checked.manifest
        if (
            len(docs) != len(report["items"])
            or report["summary"] != summarize(report)
            or report["batch_error"]
        ):
            raise CuratedError("report_integrity_error")
        for doc, item in zip(docs, report["items"], strict=True):
            if (
                item["document_id"] != doc["document_id"]
                or item["data_origin"] != doc["data_origin"]
            ):
                raise CuratedError("report_integrity_error")
            if not item["event_id"]:
                if item["rag_eligible"] or item["text_path"]:
                    raise CuratedError("report_integrity_error")
                continue
            if not re_event_id(item["event_id"]):
                raise CuratedError("report_integrity_error")
            artifact = artifacts.verify(item["sha256"])
            event = read_json(provenance.root / (item["event_id"] + ".json"))
            grant = authorize(doc, grants, ["read", "store"], at=timestamp(event["acquired_at"]))
            if artifact.sha256 != grant["expected_sha256"]:
                raise CuratedError("approval_checksum_mismatch")
            expected_trace = asdict(
                CuratedPublicTrace("0.1", digest(doc), digest(grants[doc["document_id"]]))
            )
            if (
                event.get("curated_public") != expected_trace
                or event.get("sha256") != artifact.sha256
                or event.get("document_id") != document_id(SOURCE_ID, doc["document_id"])
                or event.get("locator") != doc["source_url"]
                or event.get("status") != "accepted"
                or event.get("artifact_reference") != artifact.reference
                or event.get("byte_size") != artifact.byte_size
            ):
                raise CuratedError("provenance_integrity_error")
            if item["text_path"]:
                authorize(
                    doc, grants, ["read", "store", "extract"], at=timestamp(event["acquired_at"])
                )
                if item["rag_eligible"]:
                    authorize(
                        doc,
                        grants,
                        ["read", "store", "extract", "reuse", "rag"],
                        at=timestamp(event["acquired_at"]),
                    )
                raw = _report_path(state_root, item["text_path"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != item["text_sha256"] or batch is None:
                    raise CuratedError("text_integrity_error")
                entry = batch["records"][item["export_input_index"]]
                if entry["event_id"] != item["event_id"]:
                    raise CuratedError("provenance_integrity_error")
                record = read_json(path.parent / entry["record_path"], max_bytes=128 * 1024 * 1024)
                if raw.decode("utf-8") != "\n\n".join(b["text"] for b in record["content"]):
                    raise CuratedError("text_integrity_error")
                # The versioned sidecar is bound to the v0.1 record by its hash.
                # Verification does not re-extract source bytes or depend on a new parser version.
                quality = read_json(_report_path(state_root, item["quality_path"]))
                if (
                    quality["curated_quality_version"] != "0.1"
                    or quality["result"] != {k: item[k] for k in QUALITY_FIELDS}
                    or "curated_quality_sha256:" + digest(quality)
                    not in record["extraction"]["warnings"]
                ):
                    raise CuratedError("quality_integrity_error")
            elif item["rag_eligible"]:
                raise CuratedError("report_integrity_error")
        return {
            "integrity": "verified",
            "network_requests": 0,
            "rights": "historical_evidence_only_recheck_before_use",
        }
    except CuratedError:
        raise
    except Exception:
        raise CuratedError("report_integrity_error") from None


def re_event_id(value):
    import re

    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value)


def _report_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise CuratedError("report_integrity_error")
    return check_local_path(root.absolute() / path)
