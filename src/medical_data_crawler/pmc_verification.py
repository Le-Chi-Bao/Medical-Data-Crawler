"""Offline verification of PMC run records, original bytes and provenance."""

import hashlib
import json

from .catalog.store import Catalog
from .contract import validate_record
from .discovery import DiscoveryError
from .storage import ArtifactStore


def verify_corpus(output):
    artifacts = ArtifactStore(output / "originals")
    count = 0
    reports = list(output.glob("runs/*/report.json"))
    if not reports:
        raise DiscoveryError("no_runs")
    for path in reports:
        report = json.loads(path.read_text(encoding="utf-8"))
        for item in report["items"]:
            if "sha256" not in item:
                continue
            artifact = artifacts.verify(item["sha256"])
            if artifact.byte_size != item["byte_size"]:
                raise DiscoveryError("integrity_failed")
            event = json.loads((output / "events" / (item["event_id"] + ".json")).read_text())
            if event["sha256"] != artifact.sha256 or event["source_id"] != "pmc":
                raise DiscoveryError("provenance_mismatch")
            if "record" in item:
                record = json.loads((path.parent / item["record"]).read_text(encoding="utf-8"))
                validate_record(record)
                text = (path.parent / item["text"]).read_text(encoding="utf-8")
                if text != "\n\n".join(b["text"] for b in record["content"]):
                    raise DiscoveryError("text_mismatch")
                if (
                    record["original"]["sha256"] != artifact.sha256
                    or record["source"]["context"] != "provenance_event:" + item["event_id"]
                    or len(item["locators"]) != len(record["content"])
                ):
                    raise DiscoveryError("provenance_mismatch")
                if (
                    hashlib.sha256((path.parent / item["record"]).read_bytes()).hexdigest()
                    != item["record_sha256"]
                ):
                    raise DiscoveryError("record_mismatch")
            count += 1
    with Catalog(output / "catalog", read_only=True) as catalog:
        catalog.verify()
    return {
        "integrity": "verified",
        "run_count": len(reports),
        "verified_original_references": count,
        "network_requests": 0,
    }
