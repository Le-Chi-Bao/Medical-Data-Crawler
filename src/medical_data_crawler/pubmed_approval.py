"""Read-only approval diagnostics. Never grants permission or opens a transport."""

from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from .catalog.model import CatalogError, validate_id
from .discovery import ALLOWED_FIELDS, DiscoveryError, valid_time
from .internal_import_cli import _CLIError, _read_json
from .pubmed_pilot import METADATA_OPERATIONS, SEARCH_PROFILES, read_operator_approval

_KEYS = frozenset(
    (
        "approval_id domain_id profile_id approved_query fields valid_from valid_until "
        "operations revoked source_terms_reviewed network_approved exclusive_provider_ip output_dir"
    ).split()
)
_FLAGS = {
    "source_terms_reviewed": "source_terms_not_reviewed",
    "network_approved": "network_not_approved",
    "exclusive_provider_ip": "shared_ip_uncoordinated",
}


def _output_valid(raw):
    if type(raw) is not str or not raw.strip() or any(ord(c) < 32 for c in raw):
        return False
    windows = PureWindowsPath(raw)
    # Reject remote/device paths before any filesystem lookup during offline review.
    if windows.drive.startswith("\\") or windows.drive and not windows.root:
        return False
    if any(PureWindowsPath(p).is_reserved() for p in windows.parts):
        return False
    try:
        target = Path(raw).resolve()
        # A new destination is allowed; its existing ancestors must be directories.
        return all(not p.exists() or p.is_dir() for p in (target, *target.parents))
    except (OSError, ValueError, RuntimeError):
        return False


def validate_approval(path: Path, *, at=None):
    """Return fixed codes and known schema keys only, never configuration values.

    Readiness is advisory at this instant; pilot still rereads its independent gate.
    No writes, directory creation, DNS, environment credentials or network I/O.
    """
    invalid, blocked = [], []

    def result():
        return {
            "status": "invalid_configuration"
            if invalid
            else "not_authorized"
            if blocked
            else "ready",
            "configuration_valid": not invalid,
            "ready_for_explicit_live_pilot": not invalid and not blocked,
            "network_enabled": False,
            "issues": invalid + blocked,
        }

    try:
        path.stat()
    except FileNotFoundError:
        invalid.append({"code": "approval_missing"})
        return result()
    except OSError:
        invalid.append({"code": "approval_unavailable"})
        return result()
    try:
        value = _read_json(path, "invalid_json")
    except _CLIError:
        invalid.append({"code": "invalid_json_or_unreadable"})
        return result()
    if type(value) is not dict:
        invalid.append({"code": "invalid_schema"})
        return result()
    missing = _KEYS - value.keys()
    if missing:
        invalid.append({"code": "missing_keys", "keys": sorted(missing)})
    if value.keys() - _KEYS:
        invalid.append({"code": "unexpected_keys"})
    if invalid:
        return result()
    for key in ("approval_id", "domain_id"):
        try:
            validate_id(value[key])
        except CatalogError:
            invalid.append({"code": "invalid_identifier", "field": key})
    profile = value["profile_id"]
    if type(profile) is not str or profile not in SEARCH_PROFILES:
        invalid.append({"code": "invalid_profile"})
    elif value["approved_query"] != SEARCH_PROFILES[profile]:
        invalid.append({"code": "query_binding_mismatch"})
    fields = value["fields"]
    if (
        type(fields) is not list
        or not all(type(f) is str for f in fields)
        or len(set(fields)) != len(fields)
        or not {"pmid"} <= set(fields) <= ALLOWED_FIELDS
    ):
        invalid.append({"code": "invalid_fields"})
    if value["operations"] != list(METADATA_OPERATIONS):
        invalid.append({"code": "invalid_operations"})
    try:
        start, end = (datetime.fromisoformat(value[k]) for k in ("valid_from", "valid_until"))
        if not valid_time(start) or not valid_time(end) or start >= end:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        invalid.append({"code": "invalid_validity_interval"})
    else:
        now = at if at is not None else datetime.now(UTC)
        if now < start:
            blocked.append({"code": "approval_not_yet_valid"})
        elif now >= end:
            blocked.append({"code": "approval_expired"})
    for key in ("revoked", *_FLAGS):
        if type(value[key]) is not bool:
            invalid.append({"code": "invalid_boolean", "field": key})
        elif key == "revoked" and value[key]:
            blocked.append({"code": "permission_revoked"})
        elif key in _FLAGS and not value[key]:
            blocked.append({"code": _FLAGS[key]})
    if not _output_valid(value["output_dir"]):
        invalid.append({"code": "invalid_output_directory"})
    if not invalid and not blocked:
        # Check compatibility with the actual reader without constructing a transport.
        try:
            read_operator_approval(path)
        except (DiscoveryError, CatalogError, OSError, ValueError, TypeError):
            invalid.append({"code": "approval_changed_or_invalid"})
    return result()
