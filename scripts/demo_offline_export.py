"""Run a local export and verification against synthetic HTML and PDF fixtures."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfWriter

from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
from medical_data_crawler.export import export_batch, verify_batch
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    root = workspace / "data/offline-export-demo"
    artifacts = ArtifactStore(root / "originals")
    provenance = ProvenanceStore(root / "events", artifacts)
    pipeline = OfflinePipeline(artifacts, LocalDocumentAdapter(artifacts, provenance))

    with TemporaryDirectory(dir=root, prefix="fixtures-") as directory:
        fixtures = Path(directory)
        html = workspace / "tests/fixtures/synthetic.html"
        partial = fixtures / "partial.html"
        partial.write_text('<p>Mẫu tổng hợp</p><img src="unused.png">', encoding="utf-8")
        pdf = fixtures / "blank.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.write(pdf)

        requests = [
            DocumentRequest(path, "synthetic-demo", path.name, f"fixture:{path.name}")
            for path in (html, partial, pdf, fixtures / "missing.html")
        ]
        rights = RecordRights("Self-authored synthetic fixtures")
        results = pipeline.process_many(requests, rights=rights)
        results.append(pipeline.process(requests[0]))
        manifest_path = export_batch(results, root / "exports", provenance)

    verification = verify_batch(manifest_path, provenance)
    if not verification.valid:
        raise SystemExit(f"Verification failed ({verification.error_code})")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(manifest_path.relative_to(workspace).as_posix())
    print(json.dumps(manifest["summary"], sort_keys=True))
    print("Verification PASS")


if __name__ == "__main__":
    main()
