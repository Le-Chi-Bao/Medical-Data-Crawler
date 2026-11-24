"""Populate and verify a persistent catalog using only invented metadata.

Source-item links express explicit identity decisions supplied by the fixture.
Identifier lookups verify those decisions after the catalog reopens.
"""

import json
from pathlib import Path

from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    Document,
    DocumentRelation,
    Identifier,
    Observation,
    PolicyReference,
    Rendition,
    Revision,
    Source,
    SourceItem,
)

WORKSPACE = Path(__file__).resolve().parents[1]
FIXTURE = WORKSPACE / "tests/fixtures/catalog_metadata.json"
ENTITY_TYPES = {
    "sources": Source,
    "documents": Document,
    "policy_references": PolicyReference,
    "source_items": SourceItem,
    "revisions": Revision,
    "identifiers": Identifier,
    "observations": Observation,
    "renditions": Rendition,
    "relations": DocumentRelation,
}


def _require(condition: bool, check: str) -> None:
    if not condition:
        raise RuntimeError(f"Synthetic catalog check failed: {check}")


def _fixture_records():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _require(fixture["fixture_version"] == 1, "fixture_version")
    domains = {entry["id"]: AccessDomain(**entry) for entry in fixture["domains"]}
    records = {domain_id: [] for domain_id in domains}
    for key, entity in ENTITY_TYPES.items():
        for entry in fixture[key]:
            if entity is Document and isinstance(entry.get("scope"), list):
                entry = {**entry, "scope": tuple(entry["scope"])}
            records[entry["domain_id"]].append(entity(**entry))
    return domains, records


def _populate(catalog: Catalog, domains, records) -> None:
    for domain_id, definition in domains.items():
        catalog.create_domain(definition)
        catalog.domain(domain_id).write(*records[domain_id])


def _inventory(catalog: Catalog, domain_ids) -> dict[str, dict[str, int]]:
    inventory = {}
    for domain_id in domain_ids:
        domain = catalog.domain(domain_id)
        inventory[domain_id] = {
            key: len(domain.list(entity)) for key, entity in ENTITY_TYPES.items()
        }
    return inventory


def _check_identity(public) -> None:
    for namespace, value in (
        ("doi", "10.999999/catalog-fixture.paper-01"),
        ("pmid", "999991001"),
        ("pmcid", "PMC999991001"),
    ):
        identifier = public.find_identifier(namespace, value)
        _require(identifier is not None and identifier.document_id == "paper", "paper_identifiers")
    source_items = [public.get(SourceItem, item_id) for item_id in ("paper", "paper-mirror")]
    _require(
        all(item is not None and item.document_id == "paper" for item in source_items),
        "explicit_source_item_links",
    )
    doi_observations = public.observations("paper", field="doi")
    _require(
        {entry.source_item_id for entry in doi_observations} == {"paper", "paper-mirror"},
        "cross_source_identifier_observations",
    )
    titles = public.observations("paper", field="title")
    _require(
        len({entry.value for entry in titles}) == 2
        and {entry.verification for entry in titles} == {"verified", "reported"}
        and len({entry.evidence for entry in titles}) == 2,
        "conflicting_title_observations",
    )
    first_chapter = public.observations("atlas-edges-a", field="title")
    second_chapter = public.observations("atlas-edges-b", field="title")
    _require(
        len(first_chapter) == len(second_chapter) == 1
        and first_chapter[0].value == second_chapter[0].value
        and first_chapter[0].source_item_id != second_chapter[0].source_item_id,
        "duplicate_titles_remain_distinct",
    )
    unclassified = public.get(Document, "unclassified")
    _require(
        unclassified is not None
        and unclassified.category == "unknown"
        and not public.observations("unclassified", field="title"),
        "unknown_category_and_missing_title",
    )


def _check_history(public) -> None:
    _require(
        {revision.id for revision in public.revisions("atlas")}
        == {"atlas-edition-1", "atlas-edition-2"},
        "two_book_editions",
    )
    isbn_first = public.find_identifier("isbn", "9780000001016")
    isbn_second = public.find_identifier("isbn", "9780000001023")
    _require(
        isbn_first is not None
        and isbn_second is not None
        and isbn_first.revision_id == "atlas-edition-1"
        and isbn_second.revision_id == "atlas-edition-2",
        "isbn_edition_ownership",
    )
    chapter_editions = {
        relation.from_document_id: relation.to_revision_id
        for relation in public.relations("atlas")
        if relation.relation_type == "chapter_of"
    }
    _require(
        chapter_editions
        == {
            "atlas-edges-a": "atlas-edition-1",
            "atlas-edges-b": "atlas-edition-2",
            "atlas-surfaces-b": "atlas-edition-2",
        },
        "chapter_edition_links",
    )
    _require(
        {revision.id: revision.status for revision in public.revisions("guideline")}
        == {"guideline-1": "superseded", "guideline-2": "active"}
        and any(
            relation.relation_type == "supersedes"
            and relation.from_revision_id == "guideline-2"
            and relation.to_revision_id == "guideline-1"
            for relation in public.relations("guideline")
        ),
        "guideline_revision_history",
    )
    _require(
        {entry.format for entry in public.renditions("paper-version-1")} == {"pdf", "jats"},
        "paper_renditions",
    )
    _require(
        any(
            relation.relation_type == "retracts"
            and relation.from_document_id == "retraction-notice"
            and relation.to_revision_id == "paper-version-1"
            for relation in public.relations("paper")
        ),
        "paper_retraction_notice",
    )
    _require(
        any(
            relation.relation_type == "publication_of"
            and relation.from_document_id == "review-publication"
            and relation.to_document_id == "review"
            for relation in public.relations("review")
        ),
        "systematic_review_publication",
    )


def run_demo(data_dir: Path) -> dict:
    """Load, verify and replay the synthetic data in an operator-chosen scratch directory."""
    domains, records = _fixture_records()
    data_dir.mkdir(parents=True, exist_ok=True)
    with Catalog(data_dir) as catalog:
        _populate(catalog, domains, records)

    with Catalog(data_dir) as catalog:
        public = catalog.domain("public-fixtures")
        internal = catalog.domain("internal-fixtures")
        _check_identity(public)
        _check_history(public)
        protocol = internal.get(Document, "hospital-protocol")
        _require(
            protocol is not None
            and protocol.category == "hospital_protocols"
            and public.get(Document, "hospital-protocol") is None
            and internal.get(Document, "paper") is None,
            "domain_scoping",
        )
        categories = sorted(
            {record.category for domain in (public, internal) for record in domain.list(Document)}
        )
        _require(len(categories) == 8 and "unknown" in categories, "category_coverage")
        counts = _inventory(catalog, domains)
        _populate(catalog, domains, records)
        _require(_inventory(catalog, domains) == counts, "idempotent_replay")
        catalog.verify()

    return {
        "fixture_version": 1,
        "categories": categories,
        "domains": counts,
        "checks": {
            "conflict_preservation_and_identity": "pass",
            "domain_scoping": "pass",
            "idempotent_replay": "pass",
            "persistence_after_reopen": "pass",
            "relations_and_revision_history": "pass",
        },
        "integrity": "pass",
    }


def main() -> None:
    print(json.dumps(run_demo(WORKSPACE / "data/catalog-demo"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
