"""Persistent catalog for scoped medical-document metadata and provenance links."""

from ._schema import SCHEMA_VERSION
from .model import (
    AccessDomain,
    CatalogError,
    Document,
    DocumentRelation,
    Identifier,
    LegacyReference,
    Observation,
    PolicyReference,
    Rendition,
    Revision,
    Source,
    SourceItem,
    normalize_identifier,
)
from .store import Catalog

__all__ = [
    "SCHEMA_VERSION",
    "AccessDomain",
    "Catalog",
    "CatalogError",
    "Document",
    "DocumentRelation",
    "Identifier",
    "LegacyReference",
    "Observation",
    "PolicyReference",
    "Rendition",
    "Revision",
    "Source",
    "SourceItem",
    "normalize_identifier",
]
