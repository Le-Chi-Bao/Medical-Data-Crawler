"""Reproducible offline legacy backfill; all documents are generated locally."""

import hashlib
import json
from pathlib import Path

from pypdf import PdfWriter

from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
from medical_data_crawler.backfill_cli import main
from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    Document,
    Rendition,
    Revision,
    Source,
    SourceItem,
)
from medical_data_crawler.export import export_batch
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore

DOMAIN = "synthetic-backfill"


def build_demo(root: Path) -> Path:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    spec = root / "inputs.jsonl"
    if spec.exists():
        return spec
    artifacts = ArtifactStore(root / "originals")
    provenance = ProvenanceStore(root / "events", artifacts)
    pipeline = OfflinePipeline(artifacts, LocalDocumentAdapter(artifacts, provenance))
    html = root / "invented.html"
    html.write_text("<html><title>Invented</title><body><p>Fixture text.</p></body></html>")
    pdf = root / "invented.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(pdf)
    envelopes = []
    with Catalog(root / "catalog") as catalog:
        catalog.create_domain(AccessDomain(DOMAIN))
        scope = catalog.domain(DOMAIN)
        scope.write(Source(DOMAIN, "provider", "Invented provider", "manual_import"))
        # Two versions of one explicitly selected logical document, plus a separate
        # source with identical HTML bytes. Hash equality never decides identity.
        for batch_number in range(2):
            results, mappings = [], []
            for index, (source, file, document) in enumerate(
                [
                    ("legacy-web", html, "document-a"),
                    ("legacy-pdf", pdf, "document-a"),
                    ("legacy-other", html, "document-b"),
                ]
            ):
                locator = f"https://example.org/{source}"
                request = DocumentRequest(file, source, "stable-key", locator)
                result = pipeline.process(request, rights=RecordRights("synthetic-fixture"))
                results.append(result)
                item_id = f"item-{source}"
                revision_id = f"{document}-v{batch_number}"
                rendition_id = f"rendition-{batch_number}-{index}"
                scope.write(
                    Document(DOMAIN, document),
                    SourceItem(DOMAIN, item_id, "provider", source, document, locator),
                    Revision(
                        DOMAIN,
                        revision_id,
                        document,
                        f"observed-{batch_number}",
                        "2026-11-24T00:00:00Z",
                    ),
                    Rendition(
                        DOMAIN,
                        rendition_id,
                        document,
                        revision_id,
                        "pdf" if file == pdf else "html",
                        source_item_id=item_id,
                        sha256=result.record["original"]["sha256"],
                        byte_size=result.record["original"]["byte_length"],
                    ),
                )
                mappings.append(
                    dict(
                        input_index=index,
                        legacy_source_id=source,
                        source_item_id=item_id,
                        rendition_id=rendition_id,
                    )
                )
            # A traceable omission: original accepted, but no access basis to build a record.
            results.append(
                pipeline.process(
                    DocumentRequest(
                        html, "legacy-omitted", "omitted", "https://example.org/omitted"
                    )
                )
            )
            manifest = export_batch(results, root / "batches", provenance)
            envelopes.append(
                dict(
                    backfill_version="0.1",
                    domain_id=DOMAIN,
                    manifest_path=manifest.relative_to(root).as_posix(),
                    manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                    mappings=mappings,
                )
            )
        catalog.verify()
    spec.write_text("".join(json.dumps(value) + "\n" for value in envelopes), encoding="utf-8")
    return spec


def run_demo(root: Path):
    spec = build_demo(root)
    arguments = [
        "--catalog",
        str(root / "catalog"),
        "--domain",
        DOMAIN,
        "--events",
        str(root / "events"),
        "--originals",
        str(root / "originals"),
        "--inputs",
        str(spec),
    ]
    for flags in ([], ["--execute"], ["--execute"]):
        if main(arguments + flags):
            raise RuntimeError("synthetic_backfill_failed")


if __name__ == "__main__":
    run_demo(Path("data/backfill-demo").resolve())
