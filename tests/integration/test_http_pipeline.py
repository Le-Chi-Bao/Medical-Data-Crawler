import json
import logging
from hashlib import sha256
from ipaddress import ip_address

from medical_data_crawler.acquisition import DocumentRequest
from medical_data_crawler.config import load_settings
from medical_data_crawler.export import export_batch, verify_batch
from medical_data_crawler.http_acquisition import HTTPAcquisitionSettings, HTTPDocumentAdapter
from medical_data_crawler.logging_setup import configure_logging
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore
from scripts.demo_http_acquisition import USER_AGENT, DemoTransport, run_demo, synthetic_source


def test_demo_exports_html_and_pdf_with_integrity(tmp_path):
    manifest_path = run_demo(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["summary"] == {
        "total": 2,
        "exported": 2,
        "failed": 0,
        "skipped": 0,
        "extraction": {"success": 2, "partial": 0, "failed": 0},
    }
    assert not manifest["omissions"]
    for expected_type, entry in zip(
        ("text/html", "application/pdf"), manifest["records"], strict=True
    ):
        record_path = manifest_path.parent / entry["record_path"]
        record = json.loads(record_path.read_text(encoding="utf-8"))
        original = tmp_path / "originals" / record["original"]["reference"]
        event_path = tmp_path / "events" / f"{entry['event_id']}.json"
        event = json.loads(event_path.read_text(encoding="utf-8"))
        assert record["original"]["media_type"] == expected_type
        assert record["extraction"]["status"] == "success" and record["content"]
        assert sha256(original.read_bytes()).hexdigest() == record["original"]["sha256"]
        assert event["http"]["attempts"][0]["status"] == 200
        assert event["sha256"] == record["original"]["sha256"]


def _pipeline(tmp_path, source, body):
    artifacts = ArtifactStore(tmp_path / "originals")
    provenance = ProvenanceStore(tmp_path / "events", artifacts)
    adapter = HTTPDocumentAdapter(
        artifacts,
        provenance,
        {"schema_version": "0.1", "sources": [source]},
        settings=HTTPAcquisitionSettings(enabled=True, user_agent=USER_AGENT, max_retries=0),
        resolver=lambda host: (ip_address("93.184.215.14"),),
        transport=DemoTransport({("publisher.example", "/sample.html"): ("text/html", body)}),
    )
    return OfflinePipeline(artifacts, adapter), provenance


def test_right_to_keep_original_does_not_authorize_extraction(tmp_path):
    source = synthetic_source("publisher.example", "/sample.html", "html")
    del source["rights"]["html_text"]
    pipeline, provenance = _pipeline(tmp_path, source, b"<p>Synthetic fixture.</p>")
    request = DocumentRequest(None, source["source_id"], "sample", source["candidate_url"])
    result = pipeline.process(request, rights=RecordRights("Synthetic fixture"))
    assert result.acquisition.accepted
    assert result.record is result.extraction is None
    assert "extraction_not_authorized" in result.warnings
    manifest_path = export_batch([result], tmp_path / "exports", provenance)
    assert verify_batch(manifest_path, provenance).valid
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["omissions"][0]["code"] == "missing_access_basis"


def test_html_grant_cannot_trigger_pdf_extraction(tmp_path, pdf_bytes):
    source = synthetic_source("publisher.example", "/sample.html", "html")
    pipeline, _ = _pipeline(tmp_path, source, pdf_bytes([[(72, 720, "Synthetic PDF")]]))
    request = DocumentRequest(None, source["source_id"], "sample", source["candidate_url"])
    result = pipeline.process(request, rights=RecordRights("Synthetic fixture"))
    assert result.acquisition.accepted
    assert result.record["extraction"]["status"] == "failed"
    assert result.record["content"] == []
    assert result.extraction.method == "offline-format-detection"


def test_failed_http_acquisition_remains_verified_omission(tmp_path):
    source = synthetic_source("publisher.example", "/sample.html", "html")
    pipeline, provenance = _pipeline(tmp_path, source, b"")
    request = DocumentRequest(None, source["source_id"], "sample", source["candidate_url"])
    result = pipeline.process(request, rights=RecordRights("Synthetic fixture"))
    assert result.errors == ("http_incomplete_response",)
    assert result.record is result.extraction is None
    manifest_path = export_batch([result], tmp_path / "exports", provenance)
    assert verify_batch(manifest_path, provenance).valid
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["omissions"][0]["event_id"] == result.acquisition.event_id


def test_application_logging_does_not_forward_parser_diagnostics(caplog, monkeypatch):
    for namespace in ("pypdf", "bs4"):
        logger = logging.getLogger(namespace)
        monkeypatch.setattr(logger, "handlers", [])
        monkeypatch.setattr(logger, "propagate", True)
    configure_logging(load_settings())
    logging.getLogger("pypdf.synthetic").warning("synthetic confidential response bytes")
    logging.getLogger("bs4.synthetic").warning("synthetic confidential response bytes")
    assert "synthetic confidential response bytes" not in caplog.text
