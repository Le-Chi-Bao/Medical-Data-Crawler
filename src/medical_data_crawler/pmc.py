"""Independent PMC vertical slice: inspected response, rights, storage and catalog."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .catalog.model import (
    AccessDomain,
    Document,
    Identifier,
    Observation,
    PolicyReference,
    Rendition,
    Revision,
    Source,
    SourceItem,
)
from .catalog.store import Catalog
from .contract import validate_record
from .discovery import DiscoveryError
from .errors import FoundationError
from .jats import extract_jats, parse_record
from .operation_policy import OperationScope
from .pmc_transport import ENDPOINT, validate_pmcid
from .provenance import ProvenanceStore, document_id
from .storage import ArtifactStore

VERSION = "1.0"
PROFILE = "pmc-oai-jats-v1"


def candidates(ids):
    if not isinstance(ids, (list, tuple)) or not 1 <= len(ids) <= 3:
        raise DiscoveryError("candidate_limit")
    values = tuple(validate_pmcid(value) for value in ids)
    if len(set(values)) != len(values):
        raise DiscoveryError("duplicate_candidate")
    return values


def scope(pmcid, operation):
    return OperationScope(
        "pmc-pilot",
        "pmc",
        operation,
        "internal_skin_lesion_corpus",
        validate_pmcid(pmcid),
        PROFILE,
        "1",
    )


def run(ids, *, transport, gate, rights, output, clock=lambda: datetime.now(UTC)):
    ids = candidates(ids)
    output = Path(output)
    run_dir = output / "runs" / uuid4().hex
    run_dir.mkdir(parents=True)
    report = dict(
        source="pmc",
        document_category="unknown",
        execution="real" if transport.is_live else "simulated",
        discovered_candidates=len(ids),
        eligible_candidates=0,
        downloaded_originals=0,
        extracted_documents=0,
        metadata_only_records=0,
        rejected_candidates=0,
        duplicates=0,
        failed_requests=0,
        missing_licenses=0,
        restricted_rights=0,
        integrity="not_checked",
        items=[],
    )
    artifacts = ArtifactStore(output / "originals")
    events = ProvenanceStore(output / "events", artifacts)
    with Catalog(output / "catalog") as catalog:
        catalog.create_domain(AccessDomain("pmc-pilot"))
        domain = catalog.domain("pmc-pilot")
        for pmcid in ids:
            item = {"pmcid": pmcid, "status": "rejected"}

            def require(operation, pmcid=pmcid):
                gate.require(pmcid + ":" + operation, scope(pmcid, operation), clock())

            try:
                require("fetch_document")
                raw = transport.fetch(pmcid, lambda: require("fetch_document"))
                article, identifiers, license_evidence = parse_record(raw, pmcid)
                review = rights.get(pmcid, {})
                if (
                    review.get("license_uri") != license_evidence["uri"]
                    or review.get("retain_original") is not True
                    or review.get("third_party_reviewed") is not True
                    or not review.get("evidence")
                ):
                    raise DiscoveryError("rights_not_established")
                require("retain_metadata")
                require("store_original")
                report["eligible_candidates"] += 1
                checksum = hashlib.sha256(raw).hexdigest()
                duplicate = (artifacts.root / checksum).exists()
                require("store_original")
                artifact = artifacts.put(raw, expected_sha256=checksum)
                acquired_at = clock()
                locator = (
                    ENDPOINT
                    + "?verb=GetRecord&metadataPrefix=pmc&identifier="
                    + "oai%3Apubmedcentral.nih.gov%3A"
                    + pmcid[3:]
                )
                event = events.record(
                    source_id="pmc",
                    logical_key=pmcid,
                    locator=locator,
                    acquired_at=acquired_at,
                    checksum=checksum,
                )
                report["downloaded_originals"] += 1
                report["duplicates"] += int(duplicate)
                item.update(
                    status="original_only",
                    sha256=checksum,
                    event_id=event,
                    byte_size=artifact.byte_size,
                )
                item["rights"] = {
                    **review,
                    "license": license_evidence,
                    "ai_use": "not_granted",
                    "distribution": "not_granted",
                    "reuse": "not_granted",
                }
                existing = domain.find_source_item("pmc", pmcid)
                doc = existing.document_id if existing else "pmc-" + pmcid
                # Only stable PMCID auto-links. DOI/PMID matches are retained as observations.
                policy = "policy-" + uuid4().hex
                revision = "rev-" + pmcid + "-" + checksum[:32]
                records = [
                    Source("pmc-pilot", "pmc", "pmc", "oai-pmh", VERSION),
                    PolicyReference(
                        "pmc-pilot",
                        policy,
                        "operator",
                        str(review["evidence"]),
                        "1",
                        license_evidence["uri"],
                    ),
                    Document("pmc-pilot", doc),
                    SourceItem("pmc-pilot", "item-" + pmcid, "pmc", pmcid, doc),
                ]
                if not domain.get(Revision, revision):
                    records.extend(
                        [
                            Revision("pmc-pilot", revision, doc, checksum, acquired_at.isoformat()),
                            Rendition(
                                "pmc-pilot",
                                "rend-" + pmcid + "-" + checksum[:32],
                                doc,
                                revision,
                                "xml",
                                source_item_id="item-" + pmcid,
                                declared_mime="application/xml",
                                detected_mime="application/xml",
                                sha256=checksum,
                                byte_size=len(raw),
                                policy_ref_id=policy,
                            ),
                        ]
                    )
                if not existing:
                    records.append(
                        Identifier(
                            "pmc-pilot",
                            "id-" + pmcid,
                            "pmcid",
                            pmcid,
                            doc,
                            "PMC OAI header and JATS article-id",
                        )
                    )
                for key, value in identifiers.items():
                    records.append(
                        Observation(
                            "pmc-pilot",
                            uuid4().hex,
                            "item-" + pmcid,
                            "external_identifier",
                            key + ":" + value,
                            "JATS article-id",
                            acquired_at.isoformat(),
                        )
                    )
                records.append(
                    Observation(
                        "pmc-pilot",
                        uuid4().hex,
                        "item-" + pmcid,
                        "license_hint",
                        license_evidence["uri"],
                        "JATS permissions/license",
                        acquired_at.isoformat(),
                    )
                )
                domain.write(
                    *records,
                    before_commit=lambda: (require("store_original"), require("retain_metadata")),
                )
                try:
                    require("extract_content")
                except DiscoveryError as error:
                    item["extraction"] = error.code
                else:
                    if review.get("extract_text") is not True:
                        item["extraction"] = "rights_not_established"
                    else:
                        result, locators = extract_jats(article)
                        record = {
                            "schema_version": "0.1",
                            "document_id": document_id("pmc", pmcid),
                            "source": {
                                "source_id": "pmc",
                                "locator": locator,
                                "acquired_at": acquired_at.isoformat(),
                                "context": "provenance_event:" + event,
                            },
                            "original": {
                                "reference": checksum,
                                "sha256": checksum,
                                "byte_length": len(raw),
                                "media_type": "application/xml",
                            },
                            "content": [b.to_dict() for b in result.blocks],
                            "metadata": result.metadata,
                            "scope": "unknown",
                            "scope_evidence": None,
                            "audience": "unknown",
                            "audience_evidence": None,
                            "extraction": {
                                "status": result.status,
                                "method": result.method,
                                "version": result.version,
                                "configuration": {"profile": result.profile},
                                "warnings": list(result.warnings),
                                "errors": list(result.errors),
                            },
                            "rights": {
                                "access_basis": str(review["evidence"]),
                                "reuse": "restricted",
                                "evidence": license_evidence["uri"],
                            },
                        }
                        validate_record(record)
                        require("extract_content")
                        require("store_original")
                        (run_dir / (pmcid + ".json")).write_text(
                            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        (run_dir / (pmcid + ".txt")).write_text(
                            "\n\n".join(b.text for b in result.blocks), encoding="utf-8"
                        )
                        item.update(
                            status=result.status,
                            locators=locators,
                            record=pmcid + ".json",
                            text=pmcid + ".txt",
                        )
                        item["record_sha256"] = hashlib.sha256(
                            (run_dir / (pmcid + ".json")).read_bytes()
                        ).hexdigest()
                        report["extracted_documents"] += int(result.status != "failed")
                artifacts.verify(checksum)
            except (FoundationError, OSError) as error:
                code = error.code if isinstance(error, DiscoveryError) else "persistence_failure"
                item["error"] = code
                item["status"] = "failed"
                if code == "missing_or_ambiguous_license":
                    report["missing_licenses"] += 1
                elif code.startswith(("permission", "rights")):
                    report["restricted_rights"] += 1
                else:
                    report["failed_requests"] += 1
                report["rejected_candidates"] += 1
            report["items"].append(item)
            if transport.is_live and item.get("error"):
                report["unattempted_candidates"] = len(ids) - len(report["items"])
                break
        catalog.verify()
    report["integrity"] = "verified" if report["downloaded_originals"] else "not_applicable"
    if any(i.get("error") == "persistence_failure" for i in report["items"]):
        report["integrity"] = "failed"
    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report, run_dir
