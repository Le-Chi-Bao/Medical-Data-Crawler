"""Offline, versioned bibliographic manifests and separate operator grants."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from ._intake_files import IntakeFileError, open_local_binary
from .catalog.model import CATEGORIES

OPERATIONS = frozenset(
    {
        "read",
        "store",
        "extract",
        "rag",
        "reuse",
        "manual_acquisition",
        "automated_acquisition",
        "download",
    }
)
MAX_JSON_BYTES = 1024 * 1024
_ID = re.compile(r"[a-z][a-z0-9._-]{0,95}")
_SHA = re.compile(r"[0-9a-f]{64}")


class CuratedError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def canonical_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_json(path, *, max_bytes=MAX_JSON_BYTES):
    try:
        with open_local_binary(Path(path).absolute()) as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise CuratedError("json_size_limit")

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise CuratedError("duplicate_json_key")
                result[key] = value
            return result

        return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)
    except (OSError, ValueError, UnicodeError, RecursionError, IntakeFileError):
        raise CuratedError("json_read_error") from None


def timestamp(value):
    try:
        if not isinstance(value, str) or "T" not in value:
            raise ValueError
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise CuratedError("invalid_timestamp") from None


def _text(value):
    try:
        return (
            isinstance(value, str)
            and bool(value.strip())
            and len(value) <= 8192
            and bool(value.encode("utf-8"))
        )
    except UnicodeError:
        return False


def _url(value):
    try:
        parsed = urlsplit(value)
        return (
            _text(value)
            and parsed.scheme == "https"
            and parsed.hostname
            and "." in parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and parsed.port is None
            and not any(c.isspace() or ord(c) < 32 for c in value)
        )
    except (TypeError, ValueError, AttributeError):
        return False


def _operations(value):
    return (
        isinstance(value, list)
        and all(isinstance(v, str) for v in value)
        and len(value) == len(set(value))
        and set(value) <= OPERATIONS
    )


def _envelope(value, version_key, list_key):
    if (
        not isinstance(value, dict)
        or set(value) != {version_key, list_key}
        or value[version_key] != "0.1"
        or not isinstance(value[list_key], list)
        or len(value[list_key]) > 1000
    ):
        raise CuratedError("invalid_envelope")
    return value[list_key]


def _validate_document(doc):
    required = {
        "document_id",
        "title",
        "publisher",
        "original_publisher",
        "source_url",
        "download_url",
        "language",
        "published_on",
        "format",
        "category",
        "scope",
        "scope_evidence",
        "local_path",
        "expected_sha256",
        "submitted_at",
        "data_origin",
        "source_status",
        "verified_at",
        "access_status",
        "rights",
        "review_notes",
    }
    if not isinstance(doc, dict) or set(doc) != required:
        raise CuratedError("invalid_document_fields")
    if (
        not isinstance(doc["document_id"], str)
        or not _ID.fullmatch(doc["document_id"])
        or not _url(doc["source_url"])
        or doc["format"] not in ("pdf", "html", "htm")
        or doc["category"] not in CATEGORIES
        or doc["data_origin"] not in ("real", "synthetic")
        or doc["source_status"] not in ("candidate", "verified")
        or doc["access_status"] not in ("public_read", "download_link", "unverified", "restricted")
        or not isinstance(doc["review_notes"], str)
    ):
        raise CuratedError("invalid_metadata")
    for key in (
        "title",
        "publisher",
        "original_publisher",
        "language",
        "local_path",
        "scope_evidence",
    ):
        if doc[key] is not None and not _text(doc[key]):
            raise CuratedError("invalid_metadata")
    if doc["download_url"] is not None and not _url(doc["download_url"]):
        raise CuratedError("invalid_download_url")
    if doc["published_on"] is not None:
        value = doc["published_on"]
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", value):
            raise CuratedError("invalid_publication_date")
        try:
            datetime.fromisoformat(
                value + ("-01-01" if len(value) == 4 else "-01" if len(value) == 7 else "")
            )
        except ValueError:
            raise CuratedError("invalid_publication_date") from None
    scope = doc["scope"]
    if (
        not isinstance(scope, list)
        or not all(isinstance(s, str) for s in scope)
        or len(set(scope)) != len(scope)
        or not set(scope) <= {f"K0{i}" for i in range(1, 9)}
        or (scope and not _text(doc["scope_evidence"]))
    ):
        raise CuratedError("invalid_scope")
    if doc["expected_sha256"] is not None and (
        not isinstance(doc["expected_sha256"], str) or not _SHA.fullmatch(doc["expected_sha256"])
    ):
        raise CuratedError("invalid_checksum")
    for key in ("verified_at", "submitted_at"):
        if doc[key] is not None:
            timestamp(doc[key])
    if doc["source_status"] == "verified" and (
        not doc["verified_at"] or not doc["title"] or not doc["publisher"]
    ):
        raise CuratedError("source_evidence_missing")
    rights = doc["rights"]
    if (
        not isinstance(rights, dict)
        or set(rights)
        != {"status", "license_uri", "evidence_url", "evidence_note", "allowed_operations"}
        or rights["status"] not in ("pending_review", "reviewed", "restricted", "rejected")
        or not _operations(rights["allowed_operations"])
    ):
        raise CuratedError("invalid_rights")
    for key in ("license_uri", "evidence_url"):
        if rights[key] is not None and not _url(rights[key]):
            raise CuratedError("invalid_rights_evidence")
    if rights["evidence_note"] is not None and not _text(rights["evidence_note"]):
        raise CuratedError("invalid_rights_evidence")
    if rights["allowed_operations"] and (
        rights["status"] != "reviewed" or not (rights["evidence_url"] or rights["evidence_note"])
    ):
        raise CuratedError("rights_evidence_missing")


def validate_document(doc):
    try:
        _validate_document(doc)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise CuratedError("invalid_metadata") from None


def validate_manifest(value):
    documents = _envelope(value, "curated_manifest_version", "documents")
    ids = set()
    for doc in documents:
        validate_document(doc)
        if doc["document_id"] in ids:
            raise CuratedError("duplicate_document_id")
        ids.add(doc["document_id"])
    return documents


def validate_approvals(value):
    grants = _envelope(value, "curated_approval_version", "approvals")
    result = {}
    for grant in grants:
        if (
            not isinstance(grant, dict)
            or set(grant)
            != {
                "document_id",
                "manifest_entry_sha256",
                "expected_sha256",
                "allowed_operations",
                "reviewer",
                "evidence",
                "expires_at",
                "active",
            }
            or not isinstance(grant["document_id"], str)
            or not _ID.fullmatch(grant["document_id"])
            or grant["document_id"] in result
            or type(grant["active"]) is not bool
            or not _text(grant["reviewer"])
            or not _text(grant["evidence"])
            or not _operations(grant["allowed_operations"])
            or any(
                not isinstance(grant[k], str) or not _SHA.fullmatch(grant[k])
                for k in ("manifest_entry_sha256", "expected_sha256")
            )
        ):
            raise CuratedError("invalid_approval")
        timestamp(grant["expires_at"])
        result[grant["document_id"]] = grant
    return result


def authorize(doc, grants, operations, *, at=None):
    rights = doc["rights"]
    if doc["source_status"] != "verified":
        raise CuratedError("source_not_verified")
    if rights["status"] != "reviewed":
        raise CuratedError("rights_not_reviewed")
    for op in operations:
        if op not in rights["allowed_operations"]:
            raise CuratedError(f"{op}_not_authorized")
    grant = grants.get(doc["document_id"])
    if not grant or not grant["active"]:
        raise CuratedError("approval_missing_or_inactive")
    if (at or datetime.now(UTC)) >= timestamp(grant["expires_at"]):
        raise CuratedError("approval_expired")
    if grant["manifest_entry_sha256"] != digest(doc):
        raise CuratedError("approval_binding_mismatch")
    if doc["expected_sha256"] and doc["expected_sha256"] != grant["expected_sha256"]:
        raise CuratedError("approval_checksum_mismatch")
    for op in operations:
        if op not in grant["allowed_operations"]:
            raise CuratedError(f"{op}_not_authorized")
    return grant
