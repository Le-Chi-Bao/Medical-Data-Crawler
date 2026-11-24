"""Offline validation and authorization for a trusted source registry snapshot."""

import json
import re
from datetime import datetime
from functools import cache
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

from .errors import FoundationError

_APPROVED = {"approved_for_manual_pilot", "approved_for_automated_fetch"}
_UNAPPROVED = {"candidate", "needs_review"}
_TRANSITIONS = {
    "candidate": {"needs_review", "rejected"},
    "needs_review": _APPROVED | {"rejected"},
    "approved_for_manual_pilot": {"needs_review", "rejected"},
    "approved_for_automated_fetch": {"needs_review", "rejected"},
    "rejected": set(),
}
_HOST_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_URL = re.compile(r"https://(?P<host>[a-z0-9.-]{1,253})(?P<path>/[A-Za-z0-9./_-]*)?")
_PUBLIC_SEGMENT = re.compile(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", re.ASCII)
_SENSITIVE_SEGMENT = re.compile(
    r"(?:^|[._-])(?:patient-id|patients|patient-records?|medical-records?|mrn|phi|"
    r"private|credentials?|tokens?|secrets?|api-?keys?|passwords?|sessions?|signed)"
    r"(?:$|[._-])"
)
_OPAQUE_SEGMENT = re.compile(r"[a-f0-9]{16,}|[0-9]{5,}|[a-z0-9]{32,}")
_ACTIONS = {"read", "internal_storage", "reuse", "distribute", "ai_use"}


class SourcePolicyError(FoundationError):
    """An invalid registry or revision, reported without echoing input values."""


@cache
def _validator() -> Draft202012Validator:
    resource = files("medical_data_crawler").joinpath("schemas/source-registry-0.1.json")
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker(formats=["date-time"]))


def _public_url(value: str) -> tuple[str, str]:
    # Accept only public HTTPS document/policy slugs, without URL normalization at use time.
    match = _URL.fullmatch(value)
    if match is None:
        raise SourcePolicyError("invalid_public_url")
    host, path = match.group("host", "path")
    labels = host.split(".")
    if (
        len(labels) < 2
        or any(re.fullmatch(_HOST_LABEL, label) is None for label in labels)
        or re.fullmatch(r"[a-z]{2,63}", labels[-1]) is None
        or labels[-1] in {"local", "localhost", "internal", "lan", "home", "corp", "onion"}
    ):
        raise SourcePolicyError("invalid_public_host")
    if path and path != "/":
        for segment in path.removesuffix("/")[1:].split("/"):
            if (
                _PUBLIC_SEGMENT.fullmatch(segment) is None
                or _SENSITIVE_SEGMENT.search(segment)
                or _OPAQUE_SEGMENT.search(segment)
                or (segment.startswith("patient-") and segment != "patient-education")
            ):
                raise SourcePolicyError("invalid_public_path")
    return host, (path or "").removesuffix("/")


def _right_allowed(source: dict, asset: str, action: str) -> bool:
    return source["rights"].get(asset, {}).get(action, {}).get("status") == "allowed"


def _review_current(source: dict, at: datetime) -> bool:
    review = source["review"]
    return review is not None and (
        datetime.fromisoformat(review["reviewed_at"])
        <= at
        < datetime.fromisoformat(review["review_again_at"])
    )


def _validate_source(source: dict) -> tuple[str, str]:
    url_key = _public_url(source["candidate_url"])
    if url_key[0] != source["domain"]:
        raise SourcePolicyError("domain_mismatch")
    for url in source["copyright_policy_urls"] + source["access_terms_urls"]:
        _public_url(url)

    terms, robots, embedded = (source[key] for key in ("terms", "robots", "embedded_assets"))
    for asset_rights in source["rights"].values():
        for right in asset_rights.values():
            _check_evidence(right["status"], right["evidence_url"])
    _check_evidence(embedded["status"], embedded["evidence_url"])
    terms_status = "unknown" if terms["manual"] == terms["automated"] == "unknown" else "known"
    _check_evidence(terms_status, terms["evidence_url"])
    if (
        terms["evidence_url"] is not None
        and terms["evidence_url"] not in source["access_terms_urls"]
    ):
        raise SourcePolicyError("unlisted_terms_evidence")

    robots_url = robots["evidence_url"]
    if robots_url is not None and robots_url != f"https://{source['domain']}/robots.txt":
        raise SourcePolicyError("invalid_robots_evidence")
    if robots["status"] == "not_checked" and (robots["user_agent"] is not None or robots_url):
        raise SourcePolicyError("unexpected_robots_evidence")
    if robots["status"] in {"allowed", "denied"} and (
        robots["user_agent"] is None or robots_url is None
    ):
        raise SourcePolicyError("missing_robots_evidence")

    review = source["review"]
    if review is not None and review["reviewed_at"] >= review["review_again_at"]:
        raise SourcePolicyError("invalid_review_window")
    status = source["status"]
    automated = source["automated_acquisition"]
    if (automated == "allowed") != (status == "approved_for_automated_fetch"):
        raise SourcePolicyError("inconsistent_automated_approval")
    if status in _APPROVED:
        if (
            review is None
            or embedded["status"] != "cleared_for_internal_storage"
            or not _right_allowed(source, "original_bytes", "read")
            or not _right_allowed(source, "original_bytes", "internal_storage")
            or {
                "privacy_review",
                "embedded_assets",
                "document_rights",
                "access_terms",
            }.intersection(source["pending_decisions"])
        ):
            raise SourcePolicyError("incomplete_original_approval")
        if status == "approved_for_manual_pilot" and terms["manual"] != "allowed":
            raise SourcePolicyError("missing_manual_access_approval")
        if status == "approved_for_automated_fetch" and (
            terms["automated"] != "allowed"
            or robots["status"] != "allowed"
            or "robots" in source["pending_decisions"]
        ):
            raise SourcePolicyError("missing_automated_access_approval")
    return url_key


def _check_evidence(status: str, url: str | None) -> None:
    if status != "unknown" and url is None:
        raise SourcePolicyError("missing_rights_evidence")
    if url is not None:
        _public_url(url)


def validate_registry(registry: object) -> None:
    """Validate decoded JSON without accessing URLs or mutating/logging the registry."""
    if not _validator().is_valid(registry):
        raise SourcePolicyError("invalid_registry_schema")
    source_ids = set()
    urls = set()
    for source in registry["sources"]:
        url_key = _validate_source(source)
        if source["source_id"] in source_ids:
            raise SourcePolicyError("duplicate_source_id")
        if url_key in urls:
            raise SourcePolicyError("duplicate_candidate_url")
        source_ids.add(source["source_id"])
        urls.add(url_key)


def _valid_time(at: datetime) -> bool:
    try:
        return isinstance(at, datetime) and at.utcoffset() is not None
    except (TypeError, ValueError, OverflowError):
        return False


def validate_registry_update(previous: object, proposed: object, *, at: datetime) -> None:
    """Validate an explicit registry revision against its predecessor and effective time."""
    validate_registry(previous)
    validate_registry(proposed)
    if not _valid_time(at):
        raise SourcePolicyError("invalid_decision_time")
    old_sources = {source["source_id"]: source for source in previous["sources"]}
    new_sources = {source["source_id"]: source for source in proposed["sources"]}
    if not old_sources.keys() <= new_sources.keys():
        raise SourcePolicyError("removed_source_id")
    for source_id, source in new_sources.items():
        old = old_sources.get(source_id)
        status = source["status"]
        if old is None:
            if status not in _UNAPPROVED:
                raise SourcePolicyError("new_source_requires_review")
            continue
        if (source["candidate_url"], source["document_type"]) != (
            old["candidate_url"],
            old["document_type"],
        ):
            raise SourcePolicyError("changed_source_identity")
        old_status = old["status"]
        old_review = old["review"]
        if status == "needs_review" and old_review is not None and source["review"] != old_review:
            raise SourcePolicyError("keep_previous_review")
        if status == old_status:
            if status in _APPROVED and source != old:
                raise SourcePolicyError("approval_requires_new_review")
            continue
        if status not in _TRANSITIONS[old_status]:
            raise SourcePolicyError("invalid_approval_transition")
        if status in _APPROVED:
            if not _review_current(source, at) or (
                old_review is not None
                and source["review"]["reviewed_at"] <= old_review["reviewed_at"]
            ):
                raise SourcePolicyError("approval_requires_current_review")


def _reviewed_source(registry: object, source_id: str, url: str, at: datetime) -> dict | None:
    if not isinstance(source_id, str) or not isinstance(url, str) or not _valid_time(at):
        return None
    try:
        validate_registry(registry)
    except SourcePolicyError:
        return None
    for source in registry["sources"]:
        if (
            source["source_id"] == source_id
            and source["candidate_url"] == url
            and source["status"] in _APPROVED
            and _review_current(source, at)
        ):
            return source
    return None


def allows_automated_fetch(
    registry: object, source_id: str, url: str, *, user_agent: str, at: datetime
) -> bool:
    """Check recorded authorization for exactly one URL and reviewed user-agent token."""
    source = _reviewed_source(registry, source_id, url, at)
    return (
        source is not None
        and source["status"] == "approved_for_automated_fetch"
        and source["robots"]["user_agent"] == user_agent
    )


def allows_manual_import(registry: object, source_id: str, url: str, *, at: datetime) -> bool:
    """Check authorization for manual pilot access and storage of the original."""
    source = _reviewed_source(registry, source_id, url, at)
    return source is not None and source["terms"]["manual"] == "allowed"


def allows_asset_use(
    registry: object, source_id: str, url: str, *, asset: str, action: str, at: datetime
) -> bool:
    """Check a specific rights grant for a held asset, independently of fetch authority."""
    if not isinstance(asset, str) or not isinstance(action, str) or action not in _ACTIONS:
        return False
    source = _reviewed_source(registry, source_id, url, at)
    return (
        source is not None
        and _right_allowed(source, asset, action)
        and (
            action != "ai_use"
            or (
                "ai_use" not in source["pending_decisions"]
                and _right_allowed(source, asset, "reuse")
            )
        )
    )
