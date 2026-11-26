"""Technical capabilities are separate from operation approvals."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SourceCapability:
    provider: str
    status: str
    categories: tuple[str, ...]
    operations: tuple[str, ...]
    endpoints: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    restrictions: str = "Separate operator approval required"
    requests_per_second: float = 1.0
    permission_requirements: tuple[str, ...] = (
        "provider-specific operation grants",
        "per-document license and rights review",
    )
    metadata_mapping: str = "Not implemented; candidate sources grant no operations"
    stable_identifier: str = "Provider-specific; no title-based identity"

    def to_dict(self):
        return asdict(self)


SOURCES = {
    "pubmed": SourceCapability(
        "pubmed",
        "implemented",
        (),
        ("discover_metadata",),
        (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        ),
        ("json",),
        metadata_mapping="Existing PubMed ESearch/ESummary bibliography mapper",
        stable_identifier="PMID",
    ),
    "pmc": SourceCapability(
        "pmc",
        "implemented",
        ("research_papers", "systematic_reviews"),
        ("reviewed_identifiers", "GetRecord", "store_original", "extract_content"),
        ("https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/",),
        ("pmc",),
        "1-3 reviewed PMCIDs; per-item rights; no pagination or linked asset fetch",
        metadata_mapping="JATS front/article-meta IDs, title, language, authors; OAI header",
        stable_identifier="PMCID",
    ),
    "bookshelf": SourceCapability("bookshelf", "candidate", ("medical_textbooks",), ()),
    "medlineplus": SourceCapability(
        "medlineplus", "candidate", ("medical_reference_websites",), ()
    ),
    "who": SourceCapability(
        "who", "pending_review", ("clinical_guidelines", "medical_reports"), ()
    ),
    "crossref": SourceCapability("crossref", "candidate", (), ()),
    "europe_pmc": SourceCapability("europe_pmc", "candidate", ("research_papers",), ()),
}
