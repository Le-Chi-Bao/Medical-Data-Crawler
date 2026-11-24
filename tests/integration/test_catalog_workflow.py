import json
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    CatalogError,
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

DOMAIN = "public-test"
PRIVATE = "internal-test"
OBSERVED = "2026-11-24T02:00:00Z"
EVIDENCE = "synthetic-fixture"
CATEGORIES = (
    "medical_textbooks",
    "clinical_guidelines",
    "research_papers",
    "systematic_reviews",
    "medical_reference_websites",
    "hospital_protocols",
    "medical_reports",
)


@pytest.fixture
def database(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain(DOMAIN))
        catalog.create_domain(AccessDomain(PRIVATE, visibility="internal"))
        yield catalog, catalog.domain(DOMAIN), catalog.domain(PRIVATE)


def source(domain=DOMAIN, item_id="item-1", *, document_id=None, source_id="publisher"):
    return (
        Source(domain, source_id, "Imaginary Linden Press", "manual_import"),
        SourceItem(domain, item_id, source_id, "fixture-key", document_id),
    )


def document(document_id, category="unknown", *, domain=DOMAIN, kind="document"):
    return Document(
        domain,
        document_id,
        category=category,
        kind=kind,
        category_evidence=EVIDENCE if category != "unknown" else None,
    )


def observation(observation_id, value, *, domain=DOMAIN, item_id="item-1", **kwargs):
    return Observation(
        domain, observation_id, item_id, "title", value, EVIDENCE, OBSERVED, **kwargs
    )


@pytest.mark.parametrize("category", [*CATEGORIES, "unknown"])
def test_document_accepts_each_category_independent_of_scope_and_audience(database, category):
    _, scope, _ = database
    target = replace(
        document("sample-record", category),
        scope=("K02", "K07"),
        scope_evidence=EVIDENCE,
        audience="general",
        audience_evidence=EVIDENCE,
    )
    scope.write(target)
    stored = scope.get(Document, target.id)
    assert stored is not None
    assert stored.category == category
    assert tuple(stored.scope) == ("K02", "K07")
    assert stored.audience == "general"
    assert scope.list(Document, category=category) == (stored,)


def test_unknown_classification_needs_no_fabricated_evidence(database):
    _, scope, _ = database
    target = document("unclassified")
    scope.write(target)
    assert scope.get(Document, "unclassified") == target
    assert scope.observations("unclassified") == ()


def test_invalid_category_does_not_partially_commit_or_expose_input(database):
    _, scope, _ = database
    invalid = document("bad-category", "private-category-example")
    with pytest.raises(CatalogError, match="^invalid_category$"):
        scope.write(document("rolled-back"), invalid)
    assert scope.get(Document, "rolled-back") is None
    scope.write(document("later-transaction"))
    assert scope.get(Document, "later-transaction") is not None


def test_pagination_is_bounded_and_stable(database):
    _, scope, _ = database
    scope.write(*(document(key) for key in ("doc-c", "doc-a", "doc-b")))
    assert [row.id for row in scope.list(Document, limit=2)] == ["doc-a", "doc-b"]
    assert [row.id for row in scope.list(Document, after="doc-b", limit=2)] == ["doc-c"]
    for invalid in (0, True, -1, 10_000, "2"):
        with pytest.raises(CatalogError):
            scope.list(Document, limit=invalid)
    with pytest.raises(CatalogError, match="^invalid_record_type$"):
        scope.get([], "doc-a")
    with pytest.raises(CatalogError, match="^invalid_record_type$"):
        scope.list({})


def test_title_conflicts_and_unknown_never_overwrite_observations(database):
    _, scope, _ = database
    first = document("research-a", "research_papers")
    second = document("research-b", "research_papers")
    same_title = "Imaginary atlas of skin terminology"
    agreed = observation("obs-1", same_title, verification="verified", connector_version="1.2")
    conflicting = observation("obs-2", "Another source title", item_id="item-2")
    missing = observation("obs-3", None)
    same_title_different_document = observation("obs-4", same_title, item_id="item-3")
    scope.write(
        first,
        second,
        *source(document_id=first.id),
        *source(item_id="item-2", document_id=first.id, source_id="second-publisher"),
        *source(item_id="item-3", document_id=second.id, source_id="third-publisher"),
        agreed,
        conflicting,
        missing,
        same_title_different_document,
    )
    scope.write(agreed)

    observed = {item.id: item for item in scope.observations(first.id, field="title")}
    assert set(observed) == {"obs-1", "obs-2", "obs-3"}
    assert observed["obs-1"].value == same_title
    assert observed["obs-1"].verification == "verified"
    assert observed["obs-1"].connector_version == "1.2"
    assert observed["obs-1"].evidence == EVIDENCE
    assert observed["obs-1"].source_item_id == "item-1"
    assert observed["obs-2"].value == "Another source title"
    assert observed["obs-2"].source_item_id == "item-2"
    assert observed["obs-3"].value is None
    assert [row.value for row in scope.observations(second.id)] == [same_title]
    assert len(scope.list(Document)) == 2

    with pytest.raises(CatalogError, match="^record_conflict$"):
        scope.write(replace(agreed, value="replacement"))
    assert {item.id: item for item in scope.observations(first.id, field="title")} == observed


def test_source_item_link_is_explicit_and_replayed_idempotently(database):
    _, scope, _ = database
    origin, item = source()
    first = document("first")
    second = document("second")
    scope.write(origin, item, first, second)
    assert scope.get(SourceItem, item.id).document_id is None
    linked = replace(item, document_id=first.id)
    scope.write(linked)
    scope.write(linked)
    assert scope.get(SourceItem, item.id) == linked
    with pytest.raises(CatalogError, match="^record_conflict$"):
        scope.write(replace(item, document_id=second.id))
    assert scope.get(SourceItem, item.id) == linked
    assert scope.find_source_item(origin.id, item.native_key) == linked
    assert scope.find_source_item(origin.id, "unrecognized-key") is None
    with pytest.raises(CatalogError):
        scope.find_source_item(origin.id, "x" * 100_000)


def test_observation_list_metadata_round_trips_as_tuples(database):
    _, scope, _ = database
    authors = Observation(
        DOMAIN,
        "authors",
        "item-1",
        "authors",
        ("Imaginary Yew", "Imaginary Alder"),
        EVIDENCE,
        OBSERVED,
        normalized_value=("Yew", "Alder"),
    )
    scope.write(document("fixture"), *source(document_id="fixture"), authors)
    stored = scope.observations("fixture", field="authors")[0]
    assert stored.value == authors.value
    assert stored.normalized_value == authors.normalized_value
    scope.write(stored)
    assert scope.observations("fixture", field="authors") == (stored,)


def test_identifier_conflict_and_namespace_ownership_do_not_merge(database):
    _, scope, _ = database
    first = document("paper-a", "research_papers")
    second = document("paper-b", "research_papers")
    doi = Identifier(DOMAIN, "doi-one", "doi", "10.99999/Synthetic", first.id, EVIDENCE)
    pmid = Identifier(DOMAIN, "pmid-one", "pmid", "98900981", first.id, EVIDENCE)
    pmcid = Identifier(DOMAIN, "pmcid-two", "pmcid", "PMC98900981", second.id, EVIDENCE)
    scope.write(first, second, doi, pmid, pmcid)
    scope.write(doi)
    assert (
        scope.find_identifier("doi", "https://doi.org/10.99999/synthetic").document_id == first.id
    )
    assert scope.find_identifier("pmid", "98900981").document_id == first.id
    assert scope.find_identifier("pmcid", "pmc98900981").document_id == second.id
    with pytest.raises(CatalogError, match="^identifier_conflict$"):
        scope.write(
            replace(doi, id="doi-duplicate", value="10.99999/synthetic", document_id=second.id)
        )
    assert len(scope.list(Document)) == 2
    assert scope.get(Identifier, "doi-duplicate") is None


def test_isbn_is_edition_specific_and_chapters_keep_their_parent_version(database):
    _, scope, _ = database
    book = document("book", "medical_textbooks", kind="book")
    first = document("chapter-first", "medical_textbooks", kind="chapter")
    second = document("chapter-second", "medical_textbooks", kind="chapter")
    edition_1 = Revision(DOMAIN, "edition-one", book.id, "v1", OBSERVED, published_on="2022")
    edition_2 = Revision(DOMAIN, "edition-two", book.id, "v2", OBSERVED, published_on="2024-03")
    chapter_a = DocumentRelation(
        DOMAIN,
        "chapter-link-a",
        "chapter_of",
        first.id,
        book.id,
        EVIDENCE,
        to_revision_id=edition_1.id,
    )
    chapter_b = replace(
        chapter_a, id="chapter-link-b", from_document_id=second.id, to_revision_id=edition_2.id
    )
    isbn_a = Identifier(
        DOMAIN, "isbn-one", "isbn", "9780000000002", book.id, EVIDENCE, revision_id=edition_1.id
    )
    isbn_b = replace(isbn_a, id="isbn-two", value="9780000000019", revision_id=edition_2.id)
    edition_relation = DocumentRelation(
        DOMAIN,
        "edition-link",
        "edition_of",
        book.id,
        book.id,
        EVIDENCE,
        from_revision_id=edition_1.id,
    )
    scope.write(
        book,
        first,
        second,
        edition_1,
        edition_2,
        isbn_a,
        isbn_b,
        chapter_a,
        chapter_b,
        edition_relation,
    )
    assert scope.find_identifier("isbn", "978-0-00-000000-2").revision_id == edition_1.id
    assert scope.find_identifier("isbn", "9780000000019").revision_id == edition_2.id
    assert [row.to_revision_id for row in scope.relations(first.id)] == [edition_1.id]
    assert [row.to_revision_id for row in scope.relations(second.id)] == [edition_2.id]
    assert {row.published_on for row in scope.revisions(book.id)} == {"2022", "2024-03"}
    with pytest.raises(CatalogError):
        scope.write(replace(isbn_a, id="isbn-invalid", document_id=first.id, revision_id=None))
    with pytest.raises(CatalogError, match="^invalid_relation$"):
        scope.write(replace(chapter_a, id="second-chapter-parent", to_revision_id=edition_2.id))
    assert scope.relations(first.id) == (chapter_a,)
    assert len(scope.list(Document)) == 3


def test_guideline_history_research_renditions_publication_and_retraction(database):
    catalog, scope, _ = database
    guideline = document("guideline", "clinical_guidelines")
    paper = document("review-article", "research_papers")
    review = document("review", "systematic_reviews")
    notice = document("notice", "research_papers", kind="notice")
    old = Revision(DOMAIN, "guide-old", guideline.id, "v1", OBSERVED, effective_on="2023-01-01")
    new = Revision(DOMAIN, "guide-new", guideline.id, "v2", OBSERVED, effective_on="2024-01-01")
    paper_v1 = Revision(DOMAIN, "article-revision", paper.id, "v1", OBSERVED)
    rights = PolicyReference(DOMAIN, "rights-record", "reviewer", "fixture-approval")
    replaces = DocumentRelation(
        DOMAIN, "replaces", "supersedes", guideline.id, guideline.id, EVIDENCE, new.id, old.id
    )
    publication = DocumentRelation(
        DOMAIN, "publication", "publication_of", paper.id, review.id, EVIDENCE
    )
    retraction = DocumentRelation(
        DOMAIN, "retraction", "retracts", notice.id, paper.id, EVIDENCE, to_revision_id=paper_v1.id
    )
    scope.write(
        guideline,
        paper,
        review,
        notice,
        old,
        new,
        paper_v1,
        rights,
        Rendition(DOMAIN, "as-pdf", paper.id, paper_v1.id, "pdf", policy_ref_id=rights.id),
        Rendition(DOMAIN, "as-xml", paper.id, paper_v1.id, "xml"),
        replaces,
        publication,
        retraction,
    )
    assert {row.version_key for row in scope.revisions(guideline.id)} == {"v1", "v2"}
    assert scope.relations(guideline.id) == (replaces,)
    assert {row.format for row in scope.renditions(paper_v1.id)} == {"pdf", "xml"}
    assert scope.get(Rendition, "as-pdf").policy_ref_id == rights.id
    assert scope.get(PolicyReference, rights.id) == rights
    assert scope.relations(review.id) == (publication,)
    assert scope.relations(notice.id) == (retraction,)
    with pytest.raises(CatalogError, match="^invalid_relation$"):
        scope.write(replace(replaces, id="cycle", from_revision_id=old.id, to_revision_id=new.id))
    with pytest.raises(CatalogError, match="^invalid_relation$"):
        scope.write(replace(publication, id="wrong-kind", relation_type="unsupported"))
    with pytest.raises(CatalogError, match="^invalid_relation$"):
        scope.write(replace(retraction, id="wrong-notice", from_document_id=review.id))
    catalog.verify()


def test_equal_hash_does_not_merge_document_identities(database):
    _, scope, _ = database
    left = document("left")
    right = document("right")
    first = Revision(DOMAIN, "left-v1", left.id, "v1", OBSERVED)
    second = Revision(DOMAIN, "right-v1", right.id, "v1", OBSERVED)
    digest = "f" * 64
    scope.write(
        left,
        right,
        first,
        second,
        Rendition(DOMAIN, "same-bytes-a", left.id, first.id, "pdf", sha256=digest, byte_size=21),
        Rendition(DOMAIN, "same-bytes-b", right.id, second.id, "pdf", sha256=digest, byte_size=21),
    )
    assert {row.id for row in scope.list(Document)} == {"left", "right"}
    assert scope.renditions(first.id)[0].sha256 == scope.renditions(second.id)[0].sha256 == digest


def test_domain_api_has_no_cross_domain_lookup_or_link(database, caplog, capsys):
    catalog, public, internal = database
    private_doc = document("private-protocol", "hospital_protocols", domain=PRIVATE)
    shared_id = "same-id"
    confidential_title = "private-title-must-not-leak"
    internal.write(
        private_doc,
        document(shared_id, "hospital_protocols", domain=PRIVATE),
        *source(PRIVATE, document_id=private_doc.id),
        observation("private-observation", confidential_title, domain=PRIVATE),
        Identifier(
            PRIVATE,
            "private-id",
            "protocol",
            "unit-protocol",
            private_doc.id,
            EVIDENCE,
            issuer="synthetic-hospital",
        ),
    )
    public.write(document(shared_id), *source())
    assert public.get(Document, private_doc.id) is None
    assert public.find_identifier("protocol", "unit-protocol", issuer="synthetic-hospital") is None
    assert public.find_source_item("publisher", "fixture-key").document_id is None
    assert internal.find_source_item("publisher", "fixture-key").document_id == private_doc.id
    assert {row.id for row in public.list(Document)} == {shared_id}
    assert public.get(Document, shared_id) != internal.get(Document, shared_id)
    assert internal.observations(private_doc.id)[0].value == confidential_title

    with pytest.raises(CatalogError, match="^domain_not_found$"):
        catalog.domain("missing-domain")
    with pytest.raises(CatalogError, match="^domain_mismatch$"):
        public.write(private_doc)
    with pytest.raises(CatalogError) as raised:
        public.write(
            DocumentRelation(
                DOMAIN, "invalid-link", "translation_of", shared_id, private_doc.id, EVIDENCE
            )
        )
    assert raised.value.code in {"invalid_reference", "invalid_relation"}
    captured = capsys.readouterr()
    diagnostics = "".join(traceback.format_exception(raised.value))
    for secret in (confidential_title, private_doc.id, "unit-protocol"):
        assert secret not in diagnostics + caplog.text + captured.out + captured.err


def test_public_source_item_cannot_store_internal_locator(database):
    _, public, internal = database
    private_locator = "internal:neutral-private-item"
    origin, item = source()
    with pytest.raises(CatalogError, match="^domain_mismatch$"):
        public.write(origin, replace(item, locator=private_locator))
    assert public.get(SourceItem, item.id) is None

    origin, item = source(PRIVATE)
    internal.write(origin, replace(item, locator=private_locator))
    assert internal.get(SourceItem, item.id).locator == private_locator


def test_policy_references_must_exist_in_the_document_and_revision_domain(database):
    _, public, internal = database
    policy = PolicyReference(PRIVATE, "internal-policy", "reviewer", "synthetic-authorization")
    internal.write(policy)
    public_doc = document("fixture")
    with pytest.raises(CatalogError, match="^invalid_reference$"):
        public.write(replace(public_doc, policy_ref_id=policy.id))
    assert public.get(Document, public_doc.id) is None
    public.write(public_doc)
    revision = Revision(
        DOMAIN, "fixture-v1", public_doc.id, "v1", OBSERVED, policy_ref_id=policy.id
    )
    with pytest.raises(CatalogError, match="^invalid_reference$"):
        public.write(revision)
    assert public.revisions(public_doc.id) == ()

    internal_doc = replace(public_doc, domain_id=PRIVATE, policy_ref_id=policy.id)
    internal_revision = replace(revision, domain_id=PRIVATE)
    internal.write(internal_doc, internal_revision)
    assert internal.get(Document, internal_doc.id) == internal_doc
    assert internal.revisions(internal_doc.id)[0].policy_ref_id == policy.id


def test_rendition_and_identifier_reject_revision_with_wrong_owner(database):
    _, scope, _ = database
    left = document("left", "research_papers")
    right = document("right", "research_papers")
    revision = Revision(DOMAIN, "left-v1", left.id, "v1", OBSERVED)
    scope.write(left, right, revision)
    with pytest.raises(CatalogError, match="^invalid_reference$"):
        scope.write(Rendition(DOMAIN, "invalid", right.id, revision.id, "pdf"))
    with pytest.raises(CatalogError, match="^invalid_reference$"):
        scope.write(
            Identifier(
                DOMAIN,
                "wrong-owner",
                "doi",
                "10.99999/mismatch",
                right.id,
                EVIDENCE,
                revision_id=revision.id,
            )
        )


def test_failed_write_rolls_back_earlier_rows_and_other_writes_can_continue(database):
    catalog, scope, _ = database
    existing = document("existing")
    scope.write(existing)
    with pytest.raises(CatalogError, match="^invalid_reference$"):
        scope.write(
            document("rolled-back"),
            *source(document_id="document-that-does-not-exist"),
        )
    assert scope.get(Document, existing.id) == existing
    assert scope.get(Document, "rolled-back") is None
    assert scope.get(Source, "publisher") is None
    scope.write(document("successful-retry"), *source(document_id="successful-retry"))
    assert scope.get(SourceItem, "item-1").document_id == "successful-retry"
    catalog.verify()


@pytest.mark.parametrize(
    "bad_value",
    ["x" * 100_000, "sensitive-value\ud800", b"non-json"],
    ids=["oversized", "invalid-unicode", "non-text"],
)
def test_metadata_validation_is_bounded_and_redacts_errors(database, bad_value):
    _, scope, _ = database
    scope.write(document("fixture"), *source(document_id="fixture"))
    with pytest.raises(CatalogError) as raised:
        scope.write(observation("bad-value", bad_value))
    assert raised.value.code in {"invalid_metadata", "metadata_too_large"}
    assert "sensitive-value" not in str(raised.value)
    assert scope.observations("fixture") == ()


def test_sql_like_metadata_is_stored_as_data(database):
    catalog, scope, _ = database
    payload = "Fictional title '); DROP TABLE document; --"
    origin, item = source(document_id="fixture")
    item = replace(item, native_key=payload)
    scope.write(document("fixture"), origin, item, observation("quoted", payload))
    assert scope.observations("fixture")[0].value == payload
    assert scope.find_source_item(origin.id, payload) == item
    assert scope.find_source_item(origin.id, "' OR 1=1 --") is None
    with pytest.raises(CatalogError):
        scope.get(Document, "x' OR 1=1 --")
    assert scope.get(Document, "fixture") is not None
    catalog.verify()


def test_catalog_persists_across_process_restart(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain(DOMAIN))
        scope = catalog.domain(DOMAIN)
        scope.write(
            document("persistent"),
            *source(document_id="persistent"),
            observation("persisted-title", "Synthetic restart title"),
        )

    child = """
import json
import socket
import sys
from pathlib import Path


def blocked(*args, **kwargs):
    raise AssertionError('Network access in catalog restart test')


socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked

from medical_data_crawler.catalog import Catalog, Document

with Catalog(Path(sys.argv[1])) as catalog:
    scope = catalog.domain(sys.argv[2])
    document = scope.get(Document, 'persistent')
    observations = scope.observations(document.id)
    catalog.verify()
    print(json.dumps([document.id, observations[0].value]))
"""
    result = subprocess.run(
        [sys.executable, "-c", child, str(tmp_path), DOMAIN],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert json.loads(result.stdout) == ["persistent", "Synthetic restart title"]


def test_concurrent_connections_create_and_replay_same_records(tmp_path):
    def writer(index):
        with Catalog(tmp_path) as catalog:
            catalog.create_domain(AccessDomain(DOMAIN))
            scope = catalog.domain(DOMAIN)
            scope.write(document("shared"), document(f"writer-{index:02d}"))

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(writer, range(12)))

    with Catalog(tmp_path) as catalog:
        persisted = {row.id for row in catalog.domain(DOMAIN).list(Document)}
        assert persisted == {"shared", *(f"writer-{index:02d}" for index in range(12))}
        catalog.verify()
