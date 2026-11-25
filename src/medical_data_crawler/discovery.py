"""Trusted, offline metadata discovery contracts; no acquisition permissions."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .catalog.model import CatalogError, normalize_identifier, validate_id
from .errors import FoundationError

MAPPING_VERSION = "pubmed-esummary-2.0-v1"
FIELD_POLICY_VERSION = "pubmed-bibliography-v1"
ALLOWED_FIELDS = frozenset(
    {
        "pmid",
        "doi",
        "pmcid",
        "title",
        "authors",
        "journal",
        "published_on",
        "publication_type",
        "category",
        "status",
    }
)
MAX_RESPONSE_BYTES = 256 * 1024
MAX_PAGE_SIZE = 100
SOURCE = "pubmed"
PROFILE = "pubmed-esummary-2.0-json"


class DiscoveryError(FoundationError):
    """Fixed code only; never include submitted values or raw exceptions."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def digest(*values: object) -> str:
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def identifier(namespace: str, value: object) -> str:
    try:
        return normalize_identifier(namespace, value)[1]
    except CatalogError:
        raise DiscoveryError("invalid_identifier") from None


def valid_time(value: object) -> bool:
    try:
        return isinstance(value, datetime) and value.utcoffset() is not None
    except (ValueError, OverflowError, TypeError):
        return False


@dataclass(frozen=True, slots=True)
class SearchSnapshot:
    """Operator-pinned replay inventory; order is explicit, never a live guarantee."""

    id: str
    profile_id: str
    query: str = field(repr=False)
    pmids: tuple[str, ...]
    sort: str = "pmid-descending"

    def __post_init__(self):
        try:
            validate_id(self.id)
            validate_id(self.profile_id)
        except CatalogError:
            raise DiscoveryError("invalid_snapshot") from None
        if (
            type(self.query) is not str
            or not 1 <= len(self.query) <= 512
            or not self.query.strip()
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in self.query)
            or type(self.pmids) is not tuple
            or len(self.pmids) > 10000
            or self.sort != "pmid-descending"
        ):
            raise DiscoveryError("invalid_snapshot")
        try:
            if len(self.query.encode("utf-8")) > 512:
                raise DiscoveryError("invalid_snapshot")
        except UnicodeError:
            raise DiscoveryError("invalid_snapshot") from None
        canonical = tuple(identifier("pmid", value) for value in self.pmids)
        if (
            canonical != self.pmids
            or tuple(sorted(set(canonical), key=int, reverse=True)) != canonical
        ):
            raise DiscoveryError("invalid_snapshot")

    @property
    def fingerprint(self) -> str:
        return digest(self.id, self.profile_id, self.query, self.pmids, self.sort)


@dataclass(frozen=True, slots=True)
class DiscoveryRequest:
    domain_id: str
    profile_id: str
    query: str = field(repr=False)
    page_size: int = 2
    cursor: str | None = field(default=None, repr=False)
    source: str = SOURCE


@dataclass(frozen=True, slots=True)
class DiscoveryPermit:
    """Trusted operator input, never deserialize this from an untrusted request."""

    id: str
    domain_id: str
    profile_id: str
    query: str = field(repr=False)
    valid_from: datetime
    valid_until: datetime
    fields: frozenset[str] = ALLOWED_FIELDS
    source: str = SOURCE
    operation: str = "discover_metadata"
    retention_purpose: str = "internal_catalog_review"
    allow_discovery: bool = False
    allow_retention: bool = False
    field_policy_version: str = FIELD_POLICY_VERSION

    @property
    def fingerprint(self) -> str:
        return digest(
            self.id,
            self.domain_id,
            self.profile_id,
            self.query,
            self.source,
            self.operation,
            self.retention_purpose,
            sorted(self.fields),
            self.valid_from.isoformat(),
            self.valid_until.isoformat(),
            self.field_policy_version,
            self.allow_discovery,
            self.allow_retention,
        )


def authorize(
    request: DiscoveryRequest, permit: DiscoveryPermit, snapshot: SearchSnapshot, at: datetime
) -> None:
    if type(request) is not DiscoveryRequest or type(permit) is not DiscoveryPermit:
        raise DiscoveryError("unauthorized")
    try:
        for value in (request.domain_id, request.profile_id, permit.id, permit.domain_id):
            validate_id(value)
    except CatalogError:
        raise DiscoveryError("invalid_request") from None
    if type(request.page_size) is not int or not 1 <= request.page_size <= MAX_PAGE_SIZE:
        raise DiscoveryError("invalid_request")
    if (
        permit.allow_discovery is not True
        or permit.allow_retention is not True
        or permit.source != request.source
        or request.source != SOURCE
        or permit.domain_id != request.domain_id
        or permit.profile_id != request.profile_id
        or request.profile_id != snapshot.profile_id
        or permit.query != request.query
        or request.query != snapshot.query
        or permit.operation != "discover_metadata"
        or permit.retention_purpose != "internal_catalog_review"
        or permit.field_policy_version != FIELD_POLICY_VERSION
        or type(permit.fields) is not frozenset
        or not permit.fields <= ALLOWED_FIELDS
        or "pmid" not in permit.fields
        or not all(valid_time(t) for t in (at, permit.valid_from, permit.valid_until))
    ):
        raise DiscoveryError("unauthorized")
    if not permit.valid_from <= at < permit.valid_until:
        raise DiscoveryError("unauthorized")


class MetadataTransport(Protocol):
    """Injected trusted boundary. Must enforce max_bytes while reading in future clients."""

    def exchange(self, endpoint: str, parameters: dict[str, str], *, max_bytes: int) -> bytes: ...


class DisabledMetadataTransport:
    def exchange(self, endpoint: str, parameters: dict[str, str], *, max_bytes: int) -> bytes:
        raise DiscoveryError("network_disabled")


@dataclass(frozen=True, slots=True)
class MetadataFact:
    field: str
    value: str | tuple[str, ...] | None
    path: str


@dataclass(frozen=True, slots=True)
class DiscoveryItem:
    pmid: str
    facts: tuple[MetadataFact, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryIssue:
    code: str
    index: int | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryPage:
    total: int
    retstart: int
    items: tuple[DiscoveryItem, ...]
    issues: tuple[DiscoveryIssue, ...]
    dropped_fields: int
    next_cursor: str | None
    complete: bool


@dataclass(frozen=True, slots=True)
class SanitizedDiscoveryReport:
    status: str
    total: int | None = None
    accepted: int = 0
    rejected: int = 0
    dropped_fields: int = 0
    issues: tuple[DiscoveryIssue, ...] = ()
    report_version: str = "0.1"
