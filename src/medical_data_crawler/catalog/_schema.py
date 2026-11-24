"""On-disk SQLite contract for catalog schema 1."""

import sqlite3

from .model import CatalogError

SCHEMA_VERSION = 1
APPLICATION_ID = 0x4D444331

_SCHEMA_V1 = (
    """CREATE TABLE access_domain (
        id TEXT NOT NULL PRIMARY KEY,
        visibility TEXT NOT NULL CHECK (visibility IN ('public', 'internal'))
    )""",
    """CREATE TABLE source (
        domain_id TEXT NOT NULL REFERENCES access_domain(id),
        id TEXT NOT NULL,
        provider TEXT NOT NULL,
        channel TEXT NOT NULL,
        connector_version TEXT,
        PRIMARY KEY (domain_id, id)
    )""",
    """CREATE TABLE policy_reference (
        domain_id TEXT NOT NULL REFERENCES access_domain(id),
        id TEXT NOT NULL,
        authority TEXT NOT NULL,
        reference TEXT NOT NULL,
        policy_version TEXT,
        license_uri TEXT,
        PRIMARY KEY (domain_id, id)
    )""",
    """CREATE TABLE document (
        domain_id TEXT NOT NULL REFERENCES access_domain(id),
        id TEXT NOT NULL,
        category TEXT NOT NULL CHECK (category IN (
            'unknown', 'medical_textbooks', 'clinical_guidelines', 'research_papers',
            'systematic_reviews', 'medical_reference_websites', 'hospital_protocols',
            'medical_reports'
        )),
        kind TEXT NOT NULL CHECK (kind IN ('document', 'book', 'chapter', 'notice')),
        category_evidence TEXT,
        scope TEXT NOT NULL,
        scope_evidence TEXT,
        audience TEXT NOT NULL CHECK (audience IN ('unknown', 'general', 'medical', 'mixed')),
        audience_evidence TEXT,
        policy_ref_id TEXT,
        PRIMARY KEY (domain_id, id),
        FOREIGN KEY (domain_id, policy_ref_id) REFERENCES policy_reference(domain_id, id),
        CHECK (category = 'unknown' OR category_evidence IS NOT NULL),
        CHECK (audience = 'unknown' OR audience_evidence IS NOT NULL)
    )""",
    """CREATE TABLE source_item (
        domain_id TEXT NOT NULL,
        id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        native_key TEXT NOT NULL,
        document_id TEXT,
        locator TEXT,
        policy_ref_id TEXT,
        PRIMARY KEY (domain_id, id),
        UNIQUE (domain_id, source_id, native_key),
        UNIQUE (domain_id, document_id, id),
        FOREIGN KEY (domain_id, source_id) REFERENCES source(domain_id, id),
        FOREIGN KEY (domain_id, document_id) REFERENCES document(domain_id, id),
        FOREIGN KEY (domain_id, policy_ref_id) REFERENCES policy_reference(domain_id, id)
    )""",
    """CREATE TABLE revision (
        domain_id TEXT NOT NULL,
        id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        version_key TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        publisher_version TEXT,
        published_on TEXT,
        effective_on TEXT,
        expires_on TEXT,
        status TEXT NOT NULL,
        status_evidence TEXT,
        policy_ref_id TEXT,
        PRIMARY KEY (domain_id, id),
        UNIQUE (domain_id, document_id, id),
        UNIQUE (domain_id, document_id, version_key),
        FOREIGN KEY (domain_id, document_id) REFERENCES document(domain_id, id),
        FOREIGN KEY (domain_id, policy_ref_id) REFERENCES policy_reference(domain_id, id)
    )""",
    """CREATE TABLE identifier (
        domain_id TEXT NOT NULL,
        id TEXT NOT NULL,
        namespace TEXT NOT NULL,
        value TEXT NOT NULL,
        document_id TEXT NOT NULL,
        evidence TEXT NOT NULL,
        revision_id TEXT,
        issuer TEXT,
        canonical_value TEXT NOT NULL,
        canonical_issuer TEXT NOT NULL,
        PRIMARY KEY (domain_id, id),
        UNIQUE (domain_id, namespace, canonical_value, canonical_issuer),
        FOREIGN KEY (domain_id, document_id) REFERENCES document(domain_id, id),
        FOREIGN KEY (domain_id, document_id, revision_id)
            REFERENCES revision(domain_id, document_id, id),
        CHECK (namespace != 'isbn' OR revision_id IS NOT NULL)
    )""",
    """CREATE TABLE observation (
        domain_id TEXT NOT NULL,
        id TEXT NOT NULL,
        source_item_id TEXT NOT NULL,
        field TEXT NOT NULL,
        value TEXT NOT NULL,
        evidence TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        verification TEXT NOT NULL CHECK (verification IN ('unknown', 'reported', 'verified')),
        normalized_value TEXT NOT NULL,
        connector_version TEXT,
        PRIMARY KEY (domain_id, id),
        FOREIGN KEY (domain_id, source_item_id) REFERENCES source_item(domain_id, id)
    )""",
    """CREATE TABLE rendition (
        domain_id TEXT NOT NULL,
        id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        revision_id TEXT NOT NULL,
        format TEXT NOT NULL CHECK (format IN ('html', 'pdf', 'jats', 'xml', 'docx', 'epub',
                                               'unknown')),
        role TEXT NOT NULL CHECK (role IN ('full_text', 'supplement', 'unknown')),
        source_item_id TEXT,
        declared_mime TEXT,
        detected_mime TEXT,
        sha256 TEXT,
        byte_size INTEGER CHECK (byte_size > 0),
        policy_ref_id TEXT,
        PRIMARY KEY (domain_id, id),
        UNIQUE (domain_id, document_id, id),
        FOREIGN KEY (domain_id, document_id, revision_id)
            REFERENCES revision(domain_id, document_id, id),
        FOREIGN KEY (domain_id, document_id, source_item_id)
            REFERENCES source_item(domain_id, document_id, id),
        FOREIGN KEY (domain_id, policy_ref_id) REFERENCES policy_reference(domain_id, id),
        CHECK ((sha256 IS NULL) = (byte_size IS NULL))
    )""",
    """CREATE TABLE document_relation (
        domain_id TEXT NOT NULL,
        id TEXT NOT NULL,
        relation_type TEXT NOT NULL CHECK (relation_type IN (
            'edition_of', 'chapter_of', 'supersedes', 'translation_of', 'preprint_of',
            'corrects', 'retracts', 'withdraws', 'expression_of_concern_for', 'publication_of'
        )),
        from_document_id TEXT NOT NULL,
        to_document_id TEXT NOT NULL,
        evidence TEXT NOT NULL,
        from_revision_id TEXT,
        to_revision_id TEXT,
        PRIMARY KEY (domain_id, id),
        FOREIGN KEY (domain_id, from_document_id) REFERENCES document(domain_id, id),
        FOREIGN KEY (domain_id, to_document_id) REFERENCES document(domain_id, id),
        FOREIGN KEY (domain_id, from_document_id, from_revision_id)
            REFERENCES revision(domain_id, document_id, id),
        FOREIGN KEY (domain_id, to_document_id, to_revision_id)
            REFERENCES revision(domain_id, document_id, id)
    )""",
    """CREATE TABLE legacy_reference (
        domain_id TEXT NOT NULL,
        id TEXT NOT NULL,
        document_id TEXT NOT NULL,
        rendition_id TEXT NOT NULL,
        legacy_document_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        locator TEXT NOT NULL,
        acquired_at TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        event_id TEXT NOT NULL,
        record_sha256 TEXT NOT NULL,
        original_sha256 TEXT NOT NULL,
        PRIMARY KEY (domain_id, id),
        UNIQUE (domain_id, batch_id, event_id, record_sha256),
        FOREIGN KEY (domain_id, document_id, rendition_id)
            REFERENCES rendition(domain_id, document_id, id)
    )""",
    "CREATE INDEX document_category ON document(domain_id, category, id)",
    "CREATE INDEX observation_item ON observation(domain_id, source_item_id, field, id)",
    "CREATE INDEX rendition_revision ON rendition(domain_id, revision_id, id)",
    "CREATE INDEX relation_from ON document_relation(domain_id, from_document_id, id)",
    "CREATE INDEX relation_to ON document_relation(domain_id, to_document_id, id)",
    """CREATE UNIQUE INDEX chapter_edition ON document_relation(domain_id, from_document_id)
        WHERE relation_type = 'chapter_of'""",
    """CREATE INDEX relation_revision_from
        ON document_relation(domain_id, relation_type, from_revision_id)""",
    "CREATE INDEX legacy_document ON legacy_reference(domain_id, legacy_document_id, document_id)",
)


def bootstrap(connection: sqlite3.Connection) -> None:
    """Initialize a pristine database inside the caller's immediate transaction."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    application = connection.execute("PRAGMA application_id").fetchone()[0]
    objects = connection.execute("SELECT name, sql FROM sqlite_master").fetchall()
    if version == 0 and application == 0 and not objects:
        for statement in _SCHEMA_V1:
            connection.execute(statement)
        connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return
    if version != SCHEMA_VERSION or application != APPLICATION_ID:
        raise CatalogError("schema_version_mismatch")
    ddl = {row[1] for row in objects if not row[0].startswith("sqlite_")}
    if ddl != set(_SCHEMA_V1):
        raise CatalogError("schema_integrity_error")
