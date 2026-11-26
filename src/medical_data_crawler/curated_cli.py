"""Windows-friendly curated corpus commands. All commands operate offline."""

import argparse
import json
import sys
from pathlib import Path

from ._intake_files import IntakeFileError, check_local_path
from .curated import (
    CuratedPublicDocumentImporter,
    _report_path,
    _write_json,
    readable_report,
    summarize,
    verify_report,
)
from .curated_manifest import (
    CuratedError,
    authorize,
    digest,
    read_json,
    validate_approvals,
    validate_manifest,
)

DEFAULT_MANIFEST = "data/vietnamese-medical-corpus/sources.json"
DEFAULT_STATE = "data/vietnamese-medical-corpus"
DEFAULT_CANDIDATES = "config/vietnamese-medical-candidates.v0.1.json"


def inventory(manifest):
    docs = validate_manifest(manifest)
    report = {
        "manifest": manifest,
        "mode": "inventory",
        "batch_error": None,
        "items": [
            {
                "document_id": d["document_id"],
                "data_origin": d["data_origin"],
                "status": "not_imported",
                "event_id": None,
                "sha256": None,
                "extraction_status": None,
                "ocr_required": False,
                "rag_eligible": False,
                "code": "not_imported",
            }
            for d in docs
        ],
    }
    report["summary"] = summarize(report)
    return report


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    p = commands.add_parser("candidates", help="List researched bibliographic candidates")
    p.add_argument("--manifest", default=DEFAULT_CANDIDATES)
    p = commands.add_parser("create", help="Create a local manifest without granting rights")
    p.add_argument("--from-candidates", default=DEFAULT_CANDIDATES)
    p.add_argument("--output", default=DEFAULT_MANIFEST)
    p = commands.add_parser("approval-template", help="Write disabled operator grants for review")
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--output", required=True)
    for name in ("validate", "check-files", "fingerprints", "report"):
        p = commands.add_parser(name)
        p.add_argument("--manifest", default=DEFAULT_MANIFEST)
        p.add_argument("--base-dir", default=".")
        if name == "report":
            p.add_argument(
                "--output", help="New Markdown report path; existing files are preserved"
            )
    for name in ("import", "preview"):
        p = commands.add_parser(name)
        p.add_argument("--manifest", default=DEFAULT_MANIFEST)
        p.add_argument("--trusted-approvals", required=True)
        p.add_argument("--intake-root", default=DEFAULT_STATE + "/intake")
        p.add_argument("--state-root", default=DEFAULT_STATE)
        p.add_argument("--base-dir", default=".")
        p.add_argument("--max-bytes", type=int, default=32 * 1024 * 1024)
        if name == "import":
            p.add_argument("--dry-run", action="store_true")
    p = commands.add_parser("verify")
    p.add_argument("--report", required=True)
    p.add_argument("--state-root", default=DEFAULT_STATE)
    p = commands.add_parser("inspect-text")
    p.add_argument("--report", required=True)
    p.add_argument("--document-id", required=True)
    p.add_argument("--trusted-approvals", required=True)
    p.add_argument("--state-root", default=DEFAULT_STATE)
    return root


def _emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv=None):
    args = parser().parse_args(argv)
    # Preserve Vietnamese on redirected stdout as well as the Windows console.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.command == "create":
            value = read_json(args.from_candidates)
            validate_manifest(value)
            target = check_local_path(Path(args.output).absolute())
            _write_json(target, value)
            (target.parent / "intake").mkdir(exist_ok=True)
            _emit({"created": str(target), "rights_changed": False})
            return 0
        if args.command == "verify":
            _emit(verify_report(Path(args.report), Path(args.state_root)))
            return 0
        if args.command == "inspect-text":
            verify_report(Path(args.report), Path(args.state_root))
            report = read_json(args.report, max_bytes=128 * 1024 * 1024)
            grants = validate_approvals(read_json(args.trusted_approvals))
            doc = next(
                (
                    d
                    for d in report["manifest"]["documents"]
                    if d["document_id"] == args.document_id
                ),
                None,
            )
            if doc is None:
                raise CuratedError("document_not_found")
            authorize(doc, grants, ["read", "store", "extract"])
            item = next(i for i in report["items"] if i["document_id"] == args.document_id)
            if not item["text_path"]:
                raise CuratedError("text_not_available")
            print(
                _report_path(Path(args.state_root), item["text_path"]).read_text(encoding="utf-8")
            )
            return 0
        value = read_json(args.manifest)
        docs = validate_manifest(value)
        if args.command == "validate":
            _emit({"valid": True, "documents": len(docs)})
        elif args.command == "approval-template":
            if any(not d["expected_sha256"] for d in docs):
                raise CuratedError("expected_checksum_required_for_template")
            entries = [
                {
                    "document_id": d["document_id"],
                    "manifest_entry_sha256": digest(d),
                    "expected_sha256": d["expected_sha256"],
                    "allowed_operations": [],
                    "reviewer": "UNASSIGNED",
                    "evidence": "PENDING_REVIEW_NO_PERMISSION",
                    "expires_at": "1970-01-01T00:00:00Z",
                    "active": False,
                }
                for d in docs
            ]
            _write_json(
                check_local_path(Path(args.output).absolute()),
                {"curated_approval_version": "0.1", "approvals": entries},
            )
            _emit({"created_disabled_approvals": len(entries)})
        elif args.command == "candidates":
            _emit(
                [
                    {
                        k: d[k]
                        for k in (
                            "document_id",
                            "title",
                            "publisher",
                            "source_url",
                            "source_status",
                            "rights",
                        )
                    }
                    for d in docs
                ]
            )
        elif args.command == "fingerprints":
            _emit(
                [
                    {"document_id": d["document_id"], "manifest_entry_sha256": digest(d)}
                    for d in docs
                ]
            )
        elif args.command == "check-files":
            result = []
            for doc in docs:
                entry = {
                    "document_id": doc["document_id"],
                    "available": False,
                    "code": "local_file_not_declared",
                }
                if doc["local_path"]:
                    path = Path(doc["local_path"])
                    path = path if path.is_absolute() else Path(args.base_dir).absolute() / path
                    try:
                        path = check_local_path(path)
                        entry["available"] = path.is_file()
                        entry["code"] = None if entry["available"] else "file_not_found"
                    except IntakeFileError as error:
                        entry["code"] = error.code
                result.append(entry)
            _emit(result)
        elif args.command == "report":
            report = inventory(value)
            rendered = readable_report(report)
            if args.output:
                from .export import _publish

                target = check_local_path(Path(args.output).absolute())
                target.parent.mkdir(parents=True, exist_ok=True)
                _publish(target, rendered.encode("utf-8"))
            print(rendered)
        else:
            importer = CuratedPublicDocumentImporter(
                intake_root=Path(args.intake_root),
                state_root=Path(args.state_root),
                base_dir=Path(args.base_dir),
                approvals=read_json(args.trusted_approvals),
                max_bytes=args.max_bytes,
            )
            report = importer.run(
                value, dry_run=getattr(args, "dry_run", False), preview=args.command == "preview"
            )
            _emit(report)
            return 1 if report["batch_error"] or report["summary"]["blocked_or_failed"] else 0
        return 0
    except (CuratedError, IntakeFileError) as error:
        print(error.code, file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError):
        print("curated_io_or_configuration_error", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
