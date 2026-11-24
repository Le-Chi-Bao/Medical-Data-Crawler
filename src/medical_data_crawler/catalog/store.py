"""Transactional SQLite storage and domain-scoped catalog queries."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext, suppress
from dataclasses import fields, replace
from pathlib import Path
from typing import TypeVar

from ..provenance import ProvenanceStore
from ._legacy import read_verified_record
from ._relations import validate_relation
from ._schema import bootstrap
from .model import (
    AccessDomain,
    CatalogError,
    Document,
    DocumentRelation,
    Identifier,
    LegacyReference,
    Observation,
    PolicyReference,
    Record,
    Rendition,
    Revision,
    Source,
    SourceItem,
    encode_json,
    normalize_identifier,
    validate_category,
    validate_id,
    validate_legacy_document_id,
    validate_limit,
    validate_metadata_field,
    validate_native_key,
    validate_record,
)

DATABASE_NAME = "catalog.sqlite3"
MAX_WRITE_RECORDS = 1000

# Order also defines how records in the same atomic write refer to one another.
_TABLES = {
    PolicyReference: "policy_reference",
    Source: "source",
    Document: "document",
    SourceItem: "source_item",
    Revision: "revision",
    Identifier: "identifier",
    Observation: "observation",
    Rendition: "rendition",
    DocumentRelation: "document_relation",
    LegacyReference: "legacy_reference",
}
_ORDER = {kind: index for index, kind in enumerate(_TABLES)}
_COLUMNS = {kind: tuple(field.name for field in fields(kind)) for kind in _TABLES}
_JSON_COLUMNS = {Document: ("scope",), Observation: ("value", "normalized_value")}
RecordT = TypeVar("RecordT", bound=Record)


@contextmanager
def _database_errors() -> Iterator[None]:
    try:
        yield
    except sqlite3.IntegrityError as error:
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY:
            raise CatalogError("invalid_reference") from None
        if error.sqlite_errorcode in {
            sqlite3.SQLITE_CONSTRAINT_UNIQUE,
            sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
        }:
            raise CatalogError("record_conflict") from None
        raise CatalogError("invalid_record") from None
    except sqlite3.Error as error:
        code = getattr(error, "sqlite_errorcode", 0) or 0
        if (code & 0xFF) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            raise CatalogError("database_busy") from None
        raise CatalogError("database_error") from None


@contextmanager
def _write_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    with _database_errors():
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            connection.commit()
        except BaseException:
            with suppress(sqlite3.Error):
                connection.rollback()
            raise


def _table(kind: type[Record]) -> str:
    if type(kind) is not type or kind not in _TABLES:
        raise CatalogError("invalid_record_type")
    return _TABLES[kind]


def _record_dict(record: Record) -> dict:
    kind = type(record)
    values = {column: getattr(record, column) for column in _COLUMNS[kind]}
    for column in _JSON_COLUMNS.get(kind, ()):
        values[column] = encode_json(values[column])
    return values


def _decode(kind: type[RecordT], row: sqlite3.Row) -> RecordT:
    try:
        values = {column: row[column] for column in _COLUMNS[kind]}
        for column in _JSON_COLUMNS.get(kind, ()):
            decoded = json.loads(values[column])
            values[column] = tuple(decoded) if isinstance(decoded, list) else decoded
        return kind(**values)
    except (ValueError, TypeError, RecursionError, IndexError):
        raise CatalogError("database_integrity_error") from None


class Catalog:
    """Operator entry point. Use one connection per thread or process."""

    def __init__(self, data_dir: Path, *, read_only: bool = False):
        try:
            state = Path(data_dir).resolve()
            if not read_only:
                state.mkdir(parents=True, exist_ok=True)
            path = state / DATABASE_NAME
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise CatalogError("invalid_database_path")
        except (OSError, RuntimeError, TypeError, ValueError):
            raise CatalogError("invalid_database_path") from None

        with _database_errors():
            target = path.as_uri() + "?mode=ro" if read_only else str(path)
            self._connection = sqlite3.connect(
                target, uri=read_only, isolation_level=None, timeout=5.0
            )
            try:
                self._connection.row_factory = sqlite3.Row
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA synchronous = FULL")
                self._connection.execute("PRAGMA trusted_schema = OFF")
                if self._connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                    raise CatalogError("foreign_keys_unavailable")
                transaction = nullcontext() if read_only else _write_transaction(self._connection)
                with transaction:
                    bootstrap(self._connection)
            except BaseException:
                self._connection.close()
                raise

    def __enter__(self) -> "Catalog":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        with _database_errors():
            self._connection.close()

    def create_domain(self, domain: AccessDomain) -> None:
        if type(domain) is not AccessDomain:
            raise CatalogError("invalid_domain")
        safe = validate_record(domain)
        with _write_transaction(self._connection):
            existing = self._connection.execute(
                "SELECT visibility FROM access_domain WHERE id = ?", (safe.id,)
            ).fetchone()
            if existing is None:
                self._connection.execute(
                    "INSERT INTO access_domain VALUES (?, ?)", (safe.id, safe.visibility)
                )
            elif existing["visibility"] != safe.visibility:
                raise CatalogError("record_conflict")

    def domain(self, domain_id: str) -> "DomainCatalog":
        with _database_errors():
            row = self._connection.execute(
                "SELECT id, visibility FROM access_domain WHERE id = ?", (validate_id(domain_id),)
            ).fetchone()
        if row is None:
            raise CatalogError("domain_not_found")
        return DomainCatalog(self._connection, AccessDomain(row["id"], row["visibility"]))

    def verify(self) -> None:
        """Check SQLite structure, indexes and referential integrity without returning row data."""
        with _database_errors(), self._connection:
            self._connection.execute("BEGIN")
            integrity = self._connection.execute("PRAGMA integrity_check(1)").fetchone()
            foreign = self._connection.execute("PRAGMA foreign_key_check").fetchone()
        if integrity is None or integrity[0] != "ok" or foreign is not None:
            raise CatalogError("database_integrity_error")


class DomainCatalog:
    """An operator-selected domain. Every query and write is scoped to that domain."""

    def __init__(self, connection: sqlite3.Connection, domain: AccessDomain):
        self._connection = connection
        self._domain = domain

    @property
    def access_domain(self) -> AccessDomain:
        return self._domain

    def write(self, *records: Record) -> None:
        """Write a batch atomically. Replay is a no-op and changed facts have new IDs."""
        if len(records) > MAX_WRITE_RECORDS:
            raise CatalogError("write_too_large")
        pending = []
        for record in records:
            if type(record) not in _TABLES:
                raise CatalogError("invalid_record_type")
            if isinstance(record, LegacyReference):
                raise CatalogError("verified_link_required")
            if validate_id(record.domain_id) != self._domain.id:
                raise CatalogError("domain_mismatch")
            safe = validate_record(record)
            if (
                isinstance(safe, SourceItem)
                and self._domain.visibility == "public"
                and safe.locator is not None
                and safe.locator.startswith("internal:")
            ):
                raise CatalogError("domain_mismatch")
            pending.append(safe)
        with _write_transaction(self._connection):
            for record in sorted(pending, key=lambda record: _ORDER[type(record)]):
                self._put(record)

    def _put(self, record: Record) -> None:
        kind = type(record)
        table = _table(kind)
        values = _record_dict(record)
        existing = self.get(kind, record.id)
        if existing is not None:
            if _record_dict(existing) == values:
                return
            if isinstance(record, SourceItem) and self._link_source_item(record, existing):
                return
            raise CatalogError("record_conflict")
        if isinstance(record, Identifier):
            self._prepare_identifier(record, values)
        if isinstance(record, DocumentRelation):
            self._check_relation(record)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        self._connection.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(values.values())
        )

    def _link_source_item(self, record: SourceItem, existing: SourceItem) -> bool:
        if existing.document_id is None and record.document_id is not None:
            if existing == replace(record, document_id=None):
                self._connection.execute(
                    "UPDATE source_item SET document_id = ? WHERE domain_id = ? AND id = ?",
                    (record.document_id, self._domain.id, record.id),
                )
                return True
        # Replaying an earlier discovery may omit the binding already recorded by a reviewer.
        return record.document_id is None and record == replace(existing, document_id=None)

    def _prepare_identifier(self, record: Identifier, values: dict) -> None:
        keys = normalize_identifier(record.namespace, record.value, record.issuer)
        if record.namespace == "isbn":
            document = self.get(Document, record.document_id)
            if document is None:
                raise CatalogError("invalid_reference")
            if document.kind != "book":
                raise CatalogError("invalid_identifier")
        if self._identifier(*keys) is not None:
            raise CatalogError("identifier_conflict")
        values["canonical_value"], values["canonical_issuer"] = keys[1:]

    def _check_relation(self, relation: DocumentRelation) -> None:
        source = self.get(Document, relation.from_document_id)
        target = self.get(Document, relation.to_document_id)
        if source is None or target is None:
            raise CatalogError("invalid_reference")
        validate_relation(relation, source, target)
        if (
            relation.relation_type == "chapter_of"
            and self._connection.execute(
                "SELECT 1 FROM document_relation WHERE domain_id = ? "
                "AND relation_type = 'chapter_of' AND from_document_id = ?",
                (self._domain.id, relation.from_document_id),
            ).fetchone()
            is not None
        ):
            raise CatalogError("invalid_relation")
        if relation.relation_type == "supersedes":
            cycle = self._connection.execute(
                """WITH RECURSIVE reachable(id) AS (
                       SELECT ?
                       UNION
                       SELECT r.to_revision_id FROM reachable
                       JOIN document_relation r ON r.from_revision_id = reachable.id
                       WHERE r.domain_id = ? AND r.relation_type = 'supersedes'
                   ) SELECT 1 FROM reachable WHERE id = ? LIMIT 1""",
                (relation.to_revision_id, self._domain.id, relation.from_revision_id),
            ).fetchone()
            if cycle is not None:
                raise CatalogError("invalid_relation")

    def get(self, kind: type[RecordT], record_id: str) -> RecordT | None:
        table = _table(kind)
        with _database_errors():
            row = self._connection.execute(
                f"SELECT * FROM {table} WHERE domain_id = ? AND id = ?",
                (self._domain.id, validate_id(record_id)),
            ).fetchone()
        return _decode(kind, row) if row is not None else None

    def _page(
        self,
        kind: type[RecordT],
        limit: int,
        after: str | None,
        *,
        filter_sql: str = "",
        parameters: tuple = (),
    ) -> tuple[RecordT, ...]:
        table = _table(kind)
        cursor = "" if after is None else validate_id(after)
        with _database_errors():
            rows = self._connection.execute(
                f"SELECT * FROM {table} WHERE domain_id = ? AND id > ? {filter_sql} "
                "ORDER BY id LIMIT ?",
                (self._domain.id, cursor, *parameters, validate_limit(limit)),
            ).fetchall()
        return tuple(_decode(kind, row) for row in rows)

    def list(
        self,
        kind: type[RecordT],
        *,
        limit: int = 100,
        after: str | None = None,
        category: str | None = None,
    ) -> tuple[RecordT, ...]:
        if category is None:
            return self._page(kind, limit, after)
        if kind is not Document:
            raise CatalogError("invalid_filter")
        return self._page(
            kind,
            limit,
            after,
            filter_sql="AND category = ?",
            parameters=(validate_category(category),),
        )

    def find_identifier(
        self, namespace: str, value: str, *, issuer: str | None = None
    ) -> Identifier | None:
        return self._identifier(*normalize_identifier(namespace, value, issuer))

    def find_source_item(self, source_id: str, native_key: str) -> SourceItem | None:
        with _database_errors():
            row = self._connection.execute(
                "SELECT * FROM source_item WHERE domain_id = ? "
                "AND source_id = ? AND native_key = ?",
                (self._domain.id, validate_id(source_id), validate_native_key(native_key)),
            ).fetchone()
        return _decode(SourceItem, row) if row is not None else None

    def _identifier(self, namespace: str, value: str, issuer: str) -> Identifier | None:
        with _database_errors():
            row = self._connection.execute(
                "SELECT * FROM identifier WHERE domain_id = ? AND namespace = ? "
                "AND canonical_value = ? AND canonical_issuer = ?",
                (self._domain.id, namespace, value, issuer),
            ).fetchone()
        return _decode(Identifier, row) if row is not None else None

    def revisions(
        self, document_id: str, *, limit: int = 100, after: str | None = None
    ) -> tuple[Revision, ...]:
        return self._page(
            Revision,
            limit,
            after,
            filter_sql="AND document_id = ?",
            parameters=(validate_id(document_id),),
        )

    def renditions(
        self, revision_id: str, *, limit: int = 100, after: str | None = None
    ) -> tuple[Rendition, ...]:
        return self._page(
            Rendition,
            limit,
            after,
            filter_sql="AND revision_id = ?",
            parameters=(validate_id(revision_id),),
        )

    def observations(
        self,
        document_id: str,
        *,
        field: str | None = None,
        limit: int = 100,
        after: str | None = None,
    ) -> tuple[Observation, ...]:
        query = """AND source_item_id IN (
                       SELECT id FROM source_item WHERE domain_id = ? AND document_id = ?
                   )"""
        parameters = (self._domain.id, validate_id(document_id))
        if field is not None:
            query += " AND field = ?"
            parameters += (validate_metadata_field(field),)
        return self._page(Observation, limit, after, filter_sql=query, parameters=parameters)

    def relations(
        self, document_id: str, *, limit: int = 100, after: str | None = None
    ) -> tuple[DocumentRelation, ...]:
        key = validate_id(document_id)
        return self._page(
            DocumentRelation,
            limit,
            after,
            filter_sql="AND (from_document_id = ? OR to_document_id = ?)",
            parameters=(key, key),
        )

    def legacy_references(
        self, legacy_document_id: str, *, limit: int = 100, after: str | None = None
    ) -> tuple[LegacyReference, ...]:
        return self._page(
            LegacyReference,
            limit,
            after,
            filter_sql="AND legacy_document_id = ?",
            parameters=(validate_legacy_document_id(legacy_document_id),),
        )

    def link_verified_record(
        self,
        manifest_path: Path,
        provenance: ProvenanceStore,
        *,
        input_index: int,
        source_item_id: str,
        rendition_id: str,
    ) -> LegacyReference:
        """Attach a verified legacy record to an existing, explicitly selected rendition."""
        validate_id(source_item_id)
        validate_id(rendition_id)
        reference, media_type, byte_size = read_verified_record(
            manifest_path, provenance, input_index, self._domain
        )
        return self._link_legacy(reference, media_type, byte_size, source_item_id, rendition_id)[0]

    def _link_legacy(
        self, reference, media_type, byte_size, source_item_id, rendition_id, *, dry_run=False
    ) -> tuple[LegacyReference, bool]:
        # Dry-run never starts a write transaction. Execution rechecks every binding under lock.
        if dry_run:
            return self._prepare_legacy(
                reference, media_type, byte_size, source_item_id, rendition_id
            )
        with _write_transaction(self._connection):
            legacy, existing = self._prepare_legacy(
                reference, media_type, byte_size, source_item_id, rendition_id
            )
            self._put(legacy)
        return legacy, existing

    def _prepare_legacy(
        self, reference, media_type, byte_size, source_item_id, rendition_id
    ) -> tuple[LegacyReference, bool]:
        item = self.get(SourceItem, source_item_id)
        rendition = self.get(Rendition, rendition_id)
        if (
            item is None
            or rendition is None
            or rendition.source_item_id != item.id
            or item.document_id not in (None, rendition.document_id)
            or item.locator != reference["locator"]
            or rendition.sha256 != reference["original_sha256"]
            or rendition.byte_size != byte_size
            or {"text/html": "html", "application/pdf": "pdf"}.get(media_type) != rendition.format
        ):
            raise CatalogError("legacy_binding_mismatch")
        legacy = validate_record(
            LegacyReference(
                domain_id=self._domain.id,
                document_id=rendition.document_id,
                rendition_id=rendition.id,
                **reference,
            )
        )
        previous_owner = self._connection.execute(
            "SELECT 1 FROM legacy_reference WHERE domain_id = ? AND legacy_document_id = ? "
            "AND document_id != ? LIMIT 1",
            (self._domain.id, legacy.legacy_document_id, legacy.document_id),
        ).fetchone()
        if previous_owner is not None:
            raise CatalogError("legacy_binding_mismatch")
        existing = self.get(LegacyReference, legacy.id)
        if existing is not None and existing != legacy:
            raise CatalogError("record_conflict")
        return legacy, existing is not None
