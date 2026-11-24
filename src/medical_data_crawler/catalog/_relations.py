"""Domain rules for explicitly asserted relations."""

from .model import CatalogError, Document, DocumentRelation

_SCHOLARLY = {"research_papers", "systematic_reviews"}
_NOTICES = {"corrects", "retracts", "withdraws", "expression_of_concern_for"}


def validate_relation(relation: DocumentRelation, source: Document, target: Document) -> None:
    same_document = source.id == target.id
    start, end = relation.from_revision_id, relation.to_revision_id
    match relation.relation_type:
        case "edition_of":
            valid = same_document and source.kind == "book" and start and end is None
        case "chapter_of":
            valid = source.kind == "chapter" and target.kind == "book" and start is None and end
        case "supersedes":
            valid = same_document and start and end and start != end
        case "publication_of":
            valid = source.category == "research_papers" and target.category == "systematic_reviews"
            valid = valid and source.kind == target.kind == "document"
        case "preprint_of":
            valid = (
                not same_document
                and source.category in _SCHOLARLY
                and target.category in _SCHOLARLY
                and source.kind == target.kind == "document"
            )
        case "translation_of":
            valid = not same_document
        case kind if kind in _NOTICES:
            valid = not same_document and source.kind == "notice"
        case _:
            valid = False
    if not valid:
        raise CatalogError("invalid_relation")
