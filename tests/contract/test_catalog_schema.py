import sqlite3
from contextlib import closing

import pytest

from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    CatalogError,
    Document,
    Source,
    SourceItem,
)

DB_NAME = "catalog.sqlite3"


def test_bootstrap_is_versioned_and_reopening_preserves_rows(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain("fixture"))
        catalog.domain("fixture").write(Document("fixture", "missing-metadata"))
        catalog.verify()

    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)

    with Catalog(tmp_path) as reopened:
        scope = reopened.domain("fixture")
        assert scope.get(Document, "missing-metadata") == Document("fixture", "missing-metadata")
        reopened.verify()


def test_rejects_unrecognized_schema_version_without_applying_changes(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain("fixture"))
        catalog.domain("fixture").write(Document("fixture", "preserved"))

    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection, connection:
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(CatalogError, match="^schema_version_mismatch$"):
        Catalog(tmp_path)

    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (99,)
        assert connection.execute("SELECT id FROM document").fetchall() == [("preserved",)]


def test_rejects_an_unversioned_database_with_unrelated_tables(tmp_path):
    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection, connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO unrelated VALUES (?)", (17,))

    with pytest.raises(CatalogError):
        Catalog(tmp_path)

    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
        assert connection.execute("SELECT id FROM unrelated").fetchall() == [(17,)]


def test_rejects_schema_drift_even_when_version_matches(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain("fixture"))

    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection, connection:
        connection.execute("DROP INDEX document_category")

    with pytest.raises(CatalogError, match="^schema_integrity_error$"):
        Catalog(tmp_path)

    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection:
        assert connection.execute("SELECT id FROM access_domain").fetchall() == [("fixture",)]


def test_sqlite_rejects_cross_domain_foreign_key_even_outside_catalog_api(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain("public-test"))
        catalog.create_domain(AccessDomain("private-test", visibility="internal"))
        catalog.domain("private-test").write(Document("private-test", "private-document"))
        catalog.domain("public-test").write(
            Source("public-test", "source", "Fixture Provider", "manual_import"),
            Document("public-test", "public-document"),
            SourceItem("public-test", "source-item", "source", "native", "public-document"),
        )

    with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
            with connection:
                connection.execute(
                    "UPDATE source_item SET document_id = ? WHERE domain_id = ? AND id = ?",
                    ("private-document", "public-test", "source-item"),
                )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_verify_fails_closed_when_foreign_keys_have_been_bypassed(tmp_path):
    with Catalog(tmp_path) as catalog:
        catalog.create_domain(AccessDomain("fixture"))
        catalog.domain("fixture").write(
            Source("fixture", "source", "Fixture Provider", "manual_import"),
            SourceItem("fixture", "item", "source", "native"),
        )
        with closing(sqlite3.connect(tmp_path / DB_NAME)) as connection, connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("UPDATE source_item SET document_id = ?", ("sensitive-reference",))
        with pytest.raises(CatalogError) as raised:
            catalog.verify()
        assert "sensitive-reference" not in str(raised.value)
