"""Exercise controlled internal intake using generated synthetic documents only."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from medical_data_crawler.integrity import sha256_stream
from medical_data_crawler.internal_import import InternalIntakeGateway, parse_authorizations


def _write_pdf(path: Path) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    text = DecodedStreamObject()
    text.set_data(b"BT /F1 12 Tf 72 720 Td (Synthetic PDF document.) Tj ET")
    page.replace_contents(text)
    writer.write(path)


def _write_fixtures(root: Path) -> list[dict]:
    html = b"<!doctype html><html><body><h1>Synthetic HTML document</h1></body></html>"
    (root / "example.html").write_bytes(html)
    (root / "duplicate.htm").write_bytes(html)
    (root / "unapproved.html").write_bytes(b"<p>Unapproved synthetic document.</p>")
    (root / "broken.pdf").write_bytes(b"%PDF-1.7\nTruncated synthetic fixture")
    _write_pdf(root / "example.pdf")
    return [
        {
            "source_id": "internal-fixture",
            "logical_key": key,
            "locator": f"internal:{key}",
            "local_path": str(root / filename),
            "format": filename.rsplit(".", maxsplit=1)[-1],
            "provider_ref": "provider-fixture",
            "authorization_ref": f"approval-{key}",
            "allow_store": True,
            "allow_extract": True,
            "access_basis": "internal_authorization",
        }
        for key, filename in (
            ("fixture-html", "example.html"),
            ("fixture-broken", "broken.pdf"),
            ("fixture-duplicate", "duplicate.htm"),
            ("fixture-unapproved", "unapproved.html"),
            ("fixture-pdf", "example.pdf"),
        )
    ]


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    root = workspace / "data/internal-import-demo"
    root.mkdir(parents=True, exist_ok=True)
    state = root / "state"
    prior_events = set((state / "provenance").glob("*.json"))
    with TemporaryDirectory(dir=root, prefix="fixtures-") as directory:
        intake = Path(directory)
        documents = _write_fixtures(intake)
        expires = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        grants = [
            {
                **document,
                "active": True,
                "expires_at": expires,
                "operation": "internal_import",
                "allow_read": True,
            }
            for document in documents
            if document["logical_key"] != "fixture-unapproved"
        ]
        approvals = parse_authorizations({"authorization_version": "0.1", "authorizations": grants})
        gateway = InternalIntakeGateway(
            approved_roots=(intake,), state_root=state, authorizations=approvals
        )
        result = gateway.run({"intake_version": "0.1", "documents": documents})
        if (
            result.manifest_path is None
            or result.verification is None
            or not result.verification.valid
            or result.report["summary"]["exported"] != 3
            or result.report["summary"]["failed"] != 2
        ):
            raise SystemExit("Unexpected synthetic intake result")
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        entries = manifest["records"]
        events = set((state / "provenance").glob("*.json")) - prior_events
        if (
            len({entry["original_sha256"] for entry in entries}) != 2
            or {event.stem for event in events} != {entry["event_id"] for entry in entries}
            or len(events) != 3
            or {entry["extraction_status"] for entry in entries} != {"success"}
        ):
            raise SystemExit("Unexpected synthetic deduplication or extraction result")
        for rejected in ("unapproved.html", "broken.pdf"):
            with (intake / rejected).open("rb") as stream:
                digest = sha256_stream(stream)
            if (state / "originals" / digest).exists():
                raise SystemExit("Rejected synthetic document was stored")
        print(json.dumps(result.report, indent=2))
        print(result.manifest_path.relative_to(workspace).as_posix())
        print("Verification PASS")


if __name__ == "__main__":
    main()
