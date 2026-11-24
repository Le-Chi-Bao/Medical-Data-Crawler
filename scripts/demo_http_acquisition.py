"""Run acquisition, extraction and export using only synthetic HTTP wire responses."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.client import HTTPResponse
from io import BytesIO
from ipaddress import IPv4Address
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from medical_data_crawler.acquisition import DocumentRequest
from medical_data_crawler.export import export_batch, verify_batch
from medical_data_crawler.http_acquisition import HTTPAcquisitionSettings, HTTPDocumentAdapter
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore

USER_AGENT = "SyntheticDemoBot"


def synthetic_source(host: str, target: str, document_type: str) -> dict:
    now = datetime.now(UTC).replace(microsecond=0)
    terms = f"https://{host}/terms"
    rights = f"https://{host}/copyright"
    grant = {"status": "allowed", "evidence_url": rights}
    return {
        "source_id": f"fixture-{host.split('.')[0]}-{target[1:].replace('.', '-')}",
        "publisher": "Synthetic Fixture Publisher",
        "domain": host,
        "candidate_url": f"https://{host}{target}",
        "document_type": document_type,
        "audience_candidate": "unknown",
        "scope_candidates": [],
        "priority": "standard",
        "status": "approved_for_automated_fetch",
        "automated_acquisition": "allowed",
        "copyright_policy_urls": [rights],
        "access_terms_urls": [terms],
        "terms": {"manual": "unknown", "automated": "allowed", "evidence_url": terms},
        "robots": {
            "status": "allowed",
            "user_agent": USER_AGENT,
            "evidence_url": f"https://{host}/robots.txt",
        },
        "rights": {
            asset: {action: grant.copy() for action in ("read", "internal_storage")}
            for asset in ("original_bytes", f"{document_type}_text")
        },
        "embedded_assets": {
            "status": "cleared_for_internal_storage",
            "evidence_url": rights,
        },
        "review": {
            "reviewer_id": "reviewer-synthetic",
            "reviewed_at": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "review_again_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "pending_decisions": [],
    }


def wire_response(
    body: bytes = b"",
    *,
    status: int = 200,
    headers: tuple[tuple[str, str], ...] = (),
) -> bytes:
    lines = [f"HTTP/1.1 {status} Synthetic", *(f"{name}: {value}" for name, value in headers)]
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body


class MemorySocket:
    def __init__(self, payload: bytes):
        self.payload = payload

    def makefile(self, mode: str) -> BytesIO:
        return BytesIO(self.payload)


class DemoTransport:
    def __init__(self, documents: dict[tuple[str, str], tuple[str, bytes]]):
        self.documents = documents

    @contextmanager
    def get(self, host, target, address, user_agent, *, before_send) -> Iterator[HTTPResponse]:
        before_send()
        if user_agent != USER_AGENT:
            raise AssertionError("Unexpected synthetic User-Agent")
        media_type, body = self.documents[host, target]
        payload = wire_response(
            body, headers=(("Content-Type", media_type), ("Content-Length", str(len(body))))
        )
        with HTTPResponse(MemorySocket(payload)) as response:
            response.begin()
            yield response


def _pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Synthetic PDF fixture.) Tj ET")
    page.replace_contents(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def run_demo(root: Path) -> Path:
    workspace = Path(__file__).resolve().parents[1]
    host = "publisher.example"
    html = (workspace / "tests/fixtures/synthetic.html").read_bytes()
    documents = {
        (host, "/sample.html"): ("text/html", html),
        (host, "/sample.pdf"): ("application/pdf", _pdf()),
    }
    sources = [
        synthetic_source(domain, path, "pdf" if path.endswith(".pdf") else "html")
        for domain, path in documents
    ]
    artifacts = ArtifactStore(root / "originals")
    events = ProvenanceStore(root / "events", artifacts)
    adapter = HTTPDocumentAdapter(
        artifacts,
        events,
        {"schema_version": "0.1", "sources": sources},
        settings=HTTPAcquisitionSettings(
            enabled=True, user_agent=USER_AGENT, min_host_interval=0.01
        ),
        resolver=lambda host: (IPv4Address("93.184.215.14"),),
        transport=DemoTransport(documents),
    )
    pipeline = OfflinePipeline(artifacts, adapter)
    requests = [
        DocumentRequest(None, source["source_id"], "sample", source["candidate_url"])
        for source in sources
    ]
    results = pipeline.process_many(
        requests, rights=RecordRights("Self-authored synthetic HTTP fixtures")
    )
    if any(
        result.record is None or result.record["extraction"]["status"] != "success"
        for result in results
    ):
        raise SystemExit("Synthetic acquisition or extraction failed")
    manifest = export_batch(results, root / "exports", events)
    verification = verify_batch(manifest, events)
    if not verification.valid:
        raise SystemExit(f"Verification failed ({verification.error_code})")
    return manifest


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "data/http-acquisition-demo"
    manifest = run_demo(root)
    print(manifest.relative_to(root.parent.parent).as_posix())
    print(json.dumps(json.loads(manifest.read_text(encoding="utf-8"))["summary"], sort_keys=True))
    print("Verification PASS")
