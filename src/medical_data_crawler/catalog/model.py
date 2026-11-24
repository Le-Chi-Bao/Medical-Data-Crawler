"""Domain records and validation independent of the catalog database."""

import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from ..errors import FoundationError

CATEGORIES = frozenset(
    {
        "medical_textbooks",
        "clinical_guidelines",
        "research_papers",
        "systematic_reviews",
        "medical_reference_websites",
        "hospital_protocols",
        "medical_reports",
        "unknown",
    }
)
RELATION_TYPES = frozenset(
    {
        "edition_of",
        "chapter_of",
        "supersedes",
        "translation_of",
        "preprint_of",
        "corrects",
        "retracts",
        "withdraws",
        "expression_of_concern_for",
        "publication_of",
    }
)
FORMATS = frozenset({"html", "pdf", "jats", "xml", "docx", "epub", "unknown"})
REVISION_STATUSES = frozenset(
    {
        "unknown",
        "draft",
        "active",
        "published",
        "superseded",
        "withdrawn",
        "corrected",
        "retracted",
        "expired",
    }
)
METADATA_FIELDS = frozenset(
    {
        "title",
        "subtitle",
        "authors",
        "language",
        "publisher",
        "organization",
        "venue",
        "journal",
        "volume",
        "issue",
        "publication_type",
        "published_on",
        "updated_on",
        "effective_on",
        "expires_on",
        "edition",
        "chapter_number",
        "page_range",
        "jurisdiction",
        "population",
        "keywords",
        "study_design",
        "protocol_registration",
        "category",
        "scope",
        "audience",
        "status",
        "license_hint",
        "external_identifier",
        "doi",
        "pmid",
        "pmcid",
        "isbn",
    }
)
_SCOPE_LABELS = frozenset(f"K0{number}" for number in range(1, 9))
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_HOST_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_HOST_TLD = re.compile(r"[A-Za-z]{2,63}")
_NONPUBLIC_TLDS = frozenset({"local", "localhost", "internal", "lan", "home", "corp", "onion"})
_DOI = re.compile(r"10\.[0-9]{4,9}/[!-~]+")
_MIME = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_LEGACY_ID = re.compile(r"doc:[0-9a-f]{64}")
_LEGACY_EVENT = re.compile(r"[0-9a-f]{32}")
_UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)
_PARTIAL_DATE = re.compile(r"[0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?")
_MAX_METADATA_BYTES = 16 * 1024
_MAX_SQLITE_INTEGER = 2**63 - 1


class CatalogError(FoundationError):
    """A stable error code with no submitted field values or storage path."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class AccessDomain:
    id: str
    visibility: str = "public"


@dataclass(frozen=True, slots=True)
class Source:
    domain_id: str
    id: str
    provider: str
    channel: str
    connector_version: str | None = None


@dataclass(frozen=True, slots=True)
class SourceItem:
    domain_id: str
    id: str
    source_id: str
    native_key: str
    document_id: str | None = None
    locator: str | None = None
    policy_ref_id: str | None = None


@dataclass(frozen=True, slots=True)
class Document:
    domain_id: str
    id: str
    category: str = "unknown"
    kind: str = "document"
    category_evidence: str | None = None
    scope: str | tuple[str, ...] = "unknown"
    scope_evidence: str | None = None
    audience: str = "unknown"
    audience_evidence: str | None = None
    policy_ref_id: str | None = None


@dataclass(frozen=True, slots=True)
class Identifier:
    domain_id: str
    id: str
    namespace: str
    value: str
    document_id: str
    evidence: str
    revision_id: str | None = None
    issuer: str | None = None


MetadataValue = str | int | tuple[str, ...] | list[str] | None


@dataclass(frozen=True, slots=True)
class Observation:
    domain_id: str
    id: str
    source_item_id: str
    field: str
    value: MetadataValue
    evidence: str
    observed_at: str
    verification: str = "reported"
    normalized_value: MetadataValue = None
    connector_version: str | None = None


@dataclass(frozen=True, slots=True)
class Revision:
    domain_id: str
    id: str
    document_id: str
    version_key: str
    observed_at: str
    publisher_version: str | None = None
    published_on: str | None = None
    effective_on: str | None = None
    expires_on: str | None = None
    status: str = "unknown"
    status_evidence: str | None = None
    policy_ref_id: str | None = None


@dataclass(frozen=True, slots=True)
class Rendition:
    domain_id: str
    id: str
    document_id: str
    revision_id: str
    format: str
    role: str = "full_text"
    source_item_id: str | None = None
    declared_mime: str | None = None
    detected_mime: str | None = None
    sha256: str | None = None
    byte_size: int | None = None
    policy_ref_id: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentRelation:
    domain_id: str
    id: str
    relation_type: str
    from_document_id: str
    to_document_id: str
    evidence: str
    from_revision_id: str | None = None
    to_revision_id: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyReference:
    domain_id: str
    id: str
    authority: str
    reference: str
    policy_version: str | None = None
    license_uri: str | None = None


@dataclass(frozen=True, slots=True)
class LegacyReference:
    domain_id: str
    id: str
    document_id: str
    rendition_id: str
    legacy_document_id: str
    source_id: str
    locator: str
    acquired_at: str
    batch_id: str
    event_id: str
    record_sha256: str
    original_sha256: str


Record = (
    PolicyReference
    | Source
    | Document
    | SourceItem
    | Revision
    | Identifier
    | Observation
    | Rendition
    | DocumentRelation
    | LegacyReference
)


def _pattern(value: object, pattern: re.Pattern[str], code: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise CatalogError(code)
    return value


def validate_id(value: object) -> str:
    return _pattern(value, _ID, "invalid_id")


def validate_legacy_document_id(value: object) -> str:
    return _pattern(value, _LEGACY_ID, "invalid_legacy_reference")


def validate_limit(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 1000:
        raise CatalogError("invalid_limit")
    return value


def _choice(value: object, choices: frozenset[str], code: str) -> str:
    if type(value) is not str or value not in choices:
        raise CatalogError(code)
    return value


def validate_category(value: object) -> str:
    return _choice(value, CATEGORIES, "invalid_category")


def validate_metadata_field(value: object) -> str:
    return _choice(value, METADATA_FIELDS, "invalid_metadata")


def _text(value: object, limit: int = 1024, *, code: str = "invalid_record") -> str:
    if type(value) is not str:
        raise CatalogError(code)
    size_code = "metadata_too_large" if code == "invalid_metadata" else code
    if len(value) > limit:
        raise CatalogError(size_code)
    if not value.strip() or _CONTROL.search(value):
        raise CatalogError(code)
    try:
        byte_size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise CatalogError(code) from None
    if byte_size > limit:
        raise CatalogError(size_code)
    return value


def validate_native_key(value: object) -> str:
    return _text(value, 512)


def _optional_text(value: object, limit: int = 1024) -> None:
    if value is not None:
        _text(value, limit)


def _optional_id(value: object) -> None:
    if value is not None:
        validate_id(value)


def _evidence(value: object, required: bool) -> None:
    if required or value is not None:
        _text(value, code="invalid_evidence")


def _timestamp(value: object) -> str:
    text = _pattern(value, _UTC_TIMESTAMP, "invalid_timestamp")
    try:
        return datetime.fromisoformat(text).astimezone(UTC).isoformat()
    except (ValueError, OverflowError):
        raise CatalogError("invalid_timestamp") from None


def _date(value: object) -> None:
    if value is None:
        return
    text = _pattern(value, _PARTIAL_DATE, "invalid_date")
    suffix = {4: "-01-01", 7: "-01", 10: ""}[len(text)]
    try:
        date.fromisoformat(text + suffix)
    except ValueError:
        raise CatalogError("invalid_date") from None


def _source_locator(value: object) -> None:
    if value is None:
        return
    locator = _text(value, 2048, code="invalid_locator")
    if locator.startswith("internal:"):
        _pattern(locator.removeprefix("internal:"), _ID, "invalid_locator")
        return
    if any(character in "?#\\" or character.isspace() for character in locator):
        raise CatalogError("invalid_locator")
    try:
        parsed = urlsplit(locator)
    except ValueError:
        raise CatalogError("invalid_locator") from None
    labels = parsed.netloc.split(".")
    if (
        parsed.scheme != "https"
        or len(parsed.netloc) > 253
        or len(labels) < 2
        or any(_HOST_LABEL.fullmatch(label) is None for label in labels)
        or _HOST_TLD.fullmatch(labels[-1]) is None
        or labels[-1].lower() in _NONPUBLIC_TLDS
    ):
        raise CatalogError("invalid_locator")


def _normalize_doi(value: str) -> str:
    if not value.isascii():
        raise CatalogError("invalid_identifier")
    doi = value.lower()
    for prefix in ("https://doi.org/", "http://dx.doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi.removeprefix(prefix)
            if prefix != "doi:" and ("?" in doi or "#" in doi):
                raise CatalogError("invalid_identifier")
            break
    return _pattern(doi, _DOI, "invalid_identifier")


def _isbn13_checksum(digits: str) -> int:
    return (-sum(int(digit) * (1 if i % 2 == 0 else 3) for i, digit in enumerate(digits))) % 10


def _normalize_isbn(value: str) -> str:
    compact = value.replace("-", "").replace(" ", "").upper()
    if re.fullmatch(r"[0-9]{9}[0-9X]", compact):
        check = 10 if compact[-1] == "X" else int(compact[-1])
        weighted = sum(int(digit) * (10 - i) for i, digit in enumerate(compact[:9]))
        if (check + weighted) % 11:
            raise CatalogError("invalid_identifier")
        prefix = "978" + compact[:9]
        return prefix + str(_isbn13_checksum(prefix))
    if re.fullmatch(r"97[89][0-9]{10}", compact) and int(compact[-1]) == _isbn13_checksum(
        compact[:-1]
    ):
        return compact
    raise CatalogError("invalid_identifier")


def normalize_identifier(
    namespace: object, value: object, issuer: object = None
) -> tuple[str, str, str]:
    """Return namespace, canonical value and a key for issuer-scoped identifiers."""
    namespace = _choice(
        namespace,
        frozenset({"doi", "pmid", "pmcid", "isbn", "guideline", "protocol", "report"}),
        "invalid_identifier",
    )
    raw = _text(value, 512, code="invalid_identifier").strip()
    if namespace in {"guideline", "protocol", "report"}:
        owner = _pattern(issuer, _ID, "invalid_identifier")
        return namespace, _pattern(raw, _ID, "invalid_identifier"), owner
    if issuer is not None:
        raise CatalogError("invalid_identifier")
    if namespace == "doi":
        return namespace, _normalize_doi(raw), ""
    if namespace == "isbn":
        return namespace, _normalize_isbn(raw), ""
    if namespace == "pmid" and re.fullmatch(r"[0-9]{1,20}", raw) and int(raw) > 0:
        return namespace, str(int(raw)), ""
    if namespace == "pmcid" and re.fullmatch(r"PMC[0-9]{1,20}", raw.upper()):
        number = int(raw[3:])
        if number > 0:
            return namespace, f"PMC{number}", ""
    raise CatalogError("invalid_identifier")


def encode_json(value: object) -> str:
    """Serialize validated metadata as bounded, deterministic JSON."""
    try:
        encoded = json.dumps(
            value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        byte_size = len(encoded.encode("utf-8"))
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise CatalogError("invalid_metadata") from None
    if byte_size > _MAX_METADATA_BYTES:
        raise CatalogError("metadata_too_large")
    return encoded


def _metadata_value(field: str, value: object) -> MetadataValue:
    if value is None:
        return None
    if field in {"authors", "keywords", "scope"} and type(value) in {list, tuple}:
        if len(value) > 64:
            raise CatalogError("metadata_too_large")
        typed = tuple(_text(item, 512, code="invalid_metadata") for item in value)
        encode_json(typed)
        return typed
    if field in {"authors", "keywords"}:
        raise CatalogError("invalid_metadata")
    if field in {"chapter_number", "edition"} and type(value) is int and 1 <= value <= 10000:
        return value
    return _text(value, code="invalid_metadata")


def _document(record: Document) -> Document:
    validate_category(record.category)
    _optional_id(record.policy_ref_id)
    _choice(record.kind, frozenset({"document", "book", "chapter", "notice"}), "invalid_kind")
    if record.kind in {"book", "chapter"} and record.category not in {
        "medical_textbooks",
        "unknown",
    }:
        raise CatalogError("invalid_kind")
    _evidence(record.category_evidence, record.category != "unknown")
    _choice(
        record.audience, frozenset({"general", "medical", "mixed", "unknown"}), "invalid_audience"
    )
    _evidence(record.audience_evidence, record.audience != "unknown")
    scope = record.scope
    if type(scope) is str and scope == "unknown":
        _evidence(record.scope_evidence, False)
        return record
    if type(scope) not in {list, tuple} or len(scope) > 8:
        raise CatalogError("invalid_scope")
    labels = tuple(_choice(label, _SCOPE_LABELS, "invalid_scope") for label in scope)
    if len(labels) != len(set(labels)):
        raise CatalogError("invalid_scope")
    _evidence(record.scope_evidence, True)
    return replace(record, scope=tuple(sorted(labels)))


def _source_item(record: SourceItem) -> SourceItem:
    validate_id(record.source_id)
    validate_native_key(record.native_key)
    _optional_id(record.document_id)
    _optional_id(record.policy_ref_id)
    _source_locator(record.locator)
    return record


def _identifier(record: Identifier) -> Identifier:
    _, _, _ = normalize_identifier(record.namespace, record.value, record.issuer)
    validate_id(record.document_id)
    _optional_id(record.revision_id)
    _evidence(record.evidence, True)
    if record.namespace == "isbn" and record.revision_id is None:
        raise CatalogError("invalid_identifier")
    return record


def _observation(record: Observation) -> Observation:
    validate_id(record.source_item_id)
    validate_metadata_field(record.field)
    _choice(record.verification, frozenset({"unknown", "reported", "verified"}), "invalid_metadata")
    _evidence(record.evidence, True)
    _optional_text(record.connector_version, 128)
    return replace(
        record,
        observed_at=_timestamp(record.observed_at),
        value=_metadata_value(record.field, record.value),
        normalized_value=_metadata_value(record.field, record.normalized_value),
    )


def _revision(record: Revision) -> Revision:
    validate_id(record.document_id)
    _optional_id(record.policy_ref_id)
    _text(record.version_key, 256)
    _optional_text(record.publisher_version, 256)
    for value in (record.published_on, record.effective_on, record.expires_on):
        _date(value)
    effective, expires = record.effective_on, record.expires_on
    # A shorter date covers all matching subperiods, so overlapping precision stays valid.
    if effective and expires and effective > expires and not effective.startswith(expires):
        raise CatalogError("invalid_date")
    _choice(record.status, REVISION_STATUSES, "invalid_status")
    _evidence(record.status_evidence, record.status != "unknown")
    return replace(record, observed_at=_timestamp(record.observed_at))


def _rendition(record: Rendition) -> Rendition:
    validate_id(record.document_id)
    validate_id(record.revision_id)
    _optional_id(record.source_item_id)
    _optional_id(record.policy_ref_id)
    _choice(record.format, FORMATS, "invalid_format")
    _choice(record.role, frozenset({"full_text", "supplement", "unknown"}), "invalid_role")
    for mime in (record.declared_mime, record.detected_mime):
        if mime is not None:
            _pattern(_text(mime, 127, code="invalid_format"), _MIME, "invalid_format")
    if record.sha256 is not None or record.byte_size is not None:
        _pattern(record.sha256, _SHA256, "invalid_artifact")
        if type(record.byte_size) is not int or not 1 <= record.byte_size <= _MAX_SQLITE_INTEGER:
            raise CatalogError("invalid_artifact")
    return record


def _relation(record: DocumentRelation) -> DocumentRelation:
    _choice(record.relation_type, RELATION_TYPES, "invalid_relation")
    validate_id(record.from_document_id)
    validate_id(record.to_document_id)
    _optional_id(record.from_revision_id)
    _optional_id(record.to_revision_id)
    _evidence(record.evidence, True)
    if (record.from_document_id, record.from_revision_id) == (
        record.to_document_id,
        record.to_revision_id,
    ):
        raise CatalogError("invalid_relation")
    return record


def _policy_reference(record: PolicyReference) -> PolicyReference:
    _text(record.authority, 256)
    _text(record.reference)
    _optional_text(record.policy_version, 128)
    _optional_text(record.license_uri, 2048)
    return record


def _legacy_reference(record: LegacyReference) -> LegacyReference:
    validate_id(record.document_id)
    validate_id(record.rendition_id)
    validate_legacy_document_id(record.legacy_document_id)
    _pattern(record.batch_id, _LEGACY_EVENT, "invalid_legacy_reference")
    _pattern(record.event_id, _LEGACY_EVENT, "invalid_legacy_reference")
    _pattern(record.record_sha256, _SHA256, "invalid_legacy_reference")
    _pattern(record.original_sha256, _SHA256, "invalid_legacy_reference")
    _text(record.source_id, 512)
    _text(record.locator, 2048)
    return replace(record, acquired_at=_timestamp(record.acquired_at))


def _source(record: Source) -> Source:
    _text(record.provider, 256)
    _text(record.channel, 128)
    _optional_text(record.connector_version, 128)
    return record


_VALIDATORS = {
    PolicyReference: _policy_reference,
    Source: _source,
    Document: _document,
    SourceItem: _source_item,
    Revision: _revision,
    Identifier: _identifier,
    Observation: _observation,
    Rendition: _rendition,
    DocumentRelation: _relation,
    LegacyReference: _legacy_reference,
}


def validate_record(record: object) -> AccessDomain | Record:
    """Validate data before persistence and normalize timestamps and ordered sets."""
    if type(record) is AccessDomain:
        validate_id(record.id)
        _choice(record.visibility, frozenset({"public", "internal"}), "invalid_domain")
        return record
    validator = _VALIDATORS.get(type(record))
    if validator is None:
        raise CatalogError("invalid_record")
    validate_id(record.domain_id)
    validate_id(record.id)
    return validator(record)
