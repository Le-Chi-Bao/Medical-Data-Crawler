"""Discovery orchestration through the existing domain-scoped catalog API."""

from dataclasses import dataclass, replace

from ..discovery import (
    FIELD_POLICY_VERSION,
    MAPPING_VERSION,
    DiscoveryError,
    DiscoveryIssue,
    DiscoveryPermit,
    DiscoveryRequest,
    SanitizedDiscoveryReport,
    digest,
)
from ..pubmed import PubMedDiscoveryConnector
from .model import (
    CatalogError,
    Document,
    Identifier,
    Observation,
    PolicyReference,
    Source,
    SourceItem,
)
from .store import DomainCatalog


def local_id(domain_id: str, kind: str, *keys: object) -> str:
    return kind + "-" + digest(domain_id, "pubmed", *keys)


@dataclass(frozen=True, slots=True)
class DiscoveryOutcome:
    report: SanitizedDiscoveryReport
    next_cursor: str | None = None


class CatalogDiscoveryWriter:
    """Trusted orchestration entry point. No arbitrary caller-provided page is accepted."""

    def __init__(self, catalog: DomainCatalog, connector: PubMedDiscoveryConnector):
        self.catalog = catalog
        self.connector = connector

    def run(self, request: DiscoveryRequest, permit: DiscoveryPermit) -> DiscoveryOutcome:
        try:
            self.connector.authorize(request, permit)
            if self.catalog.access_domain.id != request.domain_id:
                raise DiscoveryError("domain_mismatch")
            page = self.connector.discover(request, permit)
        except DiscoveryError as error:
            return DiscoveryOutcome(
                SanitizedDiscoveryReport("failed", issues=(DiscoveryIssue(error.code),))
            )
        accepted = 0
        issues = list(page.issues)
        rejected = len(page.issues)
        for item in page.items:
            index = self.connector.snapshot.pmids.index(item.pmid) - page.retstart
            try:
                self.connector.authorize(request, permit)
                self._write(item, request, permit)
                accepted += 1
            except DiscoveryError as error:
                rejected += 1
                issues.append(DiscoveryIssue(error.code, index))
            except CatalogError:
                rejected += 1
                issues.append(DiscoveryIssue("catalog_write_failed", index))
        status = "incomplete" if rejected else ("complete" if page.complete else "page_committed")
        return DiscoveryOutcome(
            SanitizedDiscoveryReport(
                status, page.total, accepted, rejected, page.dropped_fields, tuple(issues)
            ),
            page.next_cursor if not rejected else None,
        )

    def _write(self, item, request, permit):
        domain = request.domain_id
        document_id = local_id(domain, "document", item.pmid)
        item_id = local_id(domain, "item", item.pmid)
        policy_id = local_id(domain, "permit", permit.fingerprint)
        evidence_base = (
            f"pubmed:esummary:2.0;pmid={item.pmid};snapshot={self.connector.snapshot.fingerprint};"
            f"permit={permit.fingerprint};mapping={MAPPING_VERSION}"
        )
        policy = PolicyReference(
            domain,
            policy_id,
            "trusted-discovery-operator",
            "discovery-retention:" + permit.fingerprint,
            FIELD_POLICY_VERSION,
        )
        category = next((f.value for f in item.facts if f.field == "category"), "unknown")
        evidence = evidence_base + ";path=pubtype" if category != "unknown" else None
        existing = self.catalog.get(Document, document_id)
        document = existing or Document(
            domain,
            document_id,
            category=category,
            category_evidence=evidence,
            policy_ref_id=policy_id,
        )
        # SourceItem and Document bind first approval; later approvals live in fact evidence.
        source_item = self.catalog.get(SourceItem, item_id) or SourceItem(
            domain,
            item_id,
            "pubmed",
            item.pmid,
            document_id,
            f"https://pubmed.ncbi.nlm.nih.gov/{item.pmid}/",
            policy_id,
        )
        if (
            source_item.source_id != "pubmed"
            or source_item.native_key != item.pmid
            or source_item.document_id != document_id
        ):
            raise DiscoveryError("identity_conflict")
        records = [
            policy,
            Source(domain, "pubmed", "NCBI PubMed", "eutilities_metadata", MAPPING_VERSION),
            document,
            source_item,
        ]
        observed = self.connector.clock().isoformat()
        for fact in item.facts:
            if fact.field not in permit.fields:
                raise DiscoveryError("unauthorized")
            evidence = evidence_base + ";path=" + fact.path
            observation_id = local_id(
                domain, "observation", item.pmid, fact.field, fact.value, evidence
            )
            observation = Observation(
                domain,
                observation_id,
                item_id,
                fact.field,
                fact.value,
                evidence,
                observed,
                connector_version=MAPPING_VERSION,
            )
            previous = self.catalog.get(Observation, observation_id)
            if previous is not None:
                # Identical claims retain the first observation time, including after restart.
                observation = replace(observation, observed_at=previous.observed_at)
            records.append(observation)
            if fact.field in {"pmid", "doi", "pmcid"}:
                identifier_id = local_id(domain, "identifier", item.pmid, fact.field, fact.value)
                owner = self.catalog.find_identifier(fact.field, fact.value)
                if owner is not None:
                    if fact.field == "pmid" and owner.document_id != document_id:
                        raise DiscoveryError("identity_conflict")
                    # Other-source DOI/PMCID hints remain observations, never merge ownership.
                    continue
                records.append(
                    Identifier(domain, identifier_id, fact.field, fact.value, document_id, evidence)
                )
        # Every item is bounded (<250 records) and atomic; another bad item cannot roll it back.
        self.connector.authorize(request, permit)
        self.catalog.write(*records)
