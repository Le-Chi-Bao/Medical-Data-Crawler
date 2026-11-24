import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from medical_data_crawler.source_policy import (
    SourcePolicyError,
    allows_asset_use,
    allows_automated_fetch,
    allows_manual_import,
    evaluate_internal_pilot_import,
    validate_registry,
    validate_registry_update,
)

_CONFIG = Path(__file__).resolve().parents[2] / "config/source_candidates.v0.1.json"
_URL = "https://publisher.example/public-guide.pdf"
_COPYRIGHT = "https://publisher.example/copyright"
_TERMS = "https://publisher.example/terms"
_ROBOTS = "https://publisher.example/robots.txt"
_AT = datetime(2026, 11, 24, tzinfo=UTC)


@pytest.fixture
def registry():
    return {
        "schema_version": "0.1",
        "sources": [
            {
                "source_id": "fixture-guide",
                "publisher": "Fixture Publisher",
                "domain": "publisher.example",
                "candidate_url": _URL,
                "document_type": "pdf",
                "audience_candidate": "unknown",
                "scope_candidates": [],
                "priority": "standard",
                "status": "needs_review",
                "rights": {},
                "copyright_policy_urls": [_COPYRIGHT],
                "access_terms_urls": [_TERMS],
                "terms": {"manual": "unknown", "automated": "unknown", "evidence_url": None},
                "robots": {"status": "not_checked", "user_agent": None, "evidence_url": None},
                "automated_acquisition": "unknown",
                "embedded_assets": {"status": "unknown", "evidence_url": None},
                "review": None,
                "pending_decisions": [],
            }
        ],
    }


def _grant(status="allowed"):
    return {"status": status, "evidence_url": _COPYRIGHT}


def _approve(registry, *, automated=False):
    source = registry["sources"][0]
    source.update(
        status="approved_for_automated_fetch" if automated else "approved_for_manual_pilot",
        terms={
            "manual": "unknown" if automated else "allowed",
            "automated": "allowed" if automated else "unknown",
            "evidence_url": _TERMS,
        },
        rights={"original_bytes": {"read": _grant(), "internal_storage": _grant()}},
        embedded_assets={"status": "cleared_for_internal_storage", "evidence_url": _COPYRIGHT},
        review={
            "reviewer_id": "reviewer-fixture",
            "reviewed_at": "2026-11-23T00:00:00Z",
            "review_again_at": "2026-12-23T00:00:00Z",
        },
    )
    if automated:
        source["automated_acquisition"] = "allowed"
        source["robots"] = {
            "status": "allowed",
            "user_agent": "FixtureBot",
            "evidence_url": _ROBOTS,
        }
    return source


def _fetch(registry, url=_URL, user_agent="FixtureBot", at=_AT):
    return allows_automated_fetch(registry, "fixture-guide", url, user_agent=user_agent, at=at)


def _use(registry, asset, action):
    return allows_asset_use(registry, "fixture-guide", _URL, asset=asset, action=action, at=_AT)


def test_packaged_schema_and_registry_candidates():
    registry = json.loads(_CONFIG.read_text(encoding="utf-8"))
    validate_registry(registry)
    assert Counter(item["publisher"] for item in registry["sources"]) == {
        "NCI": 5,
        "NIAMS": 6,
        "NHS": 5,
        "CDC": 2,
    }
    assert Counter(item["document_type"] for item in registry["sources"]) == {"html": 17, "pdf": 1}
    cdc = [source for source in registry["sources"] if source["publisher"] == "CDC"]
    assert {source["source_id"]: source["candidate_url"] for source in cdc} == {
        "cdc-tmvii-clinical-overview": (
            "https://www.cdc.gov/ringworm/hcp/clinical-overview/tmvii.html"
        ),
        "cdc-monkeypox-clinical-considerations": (
            "https://www.cdc.gov/monkeypox/hcp/clinical-overview/"
        ),
    }
    assert all(source["scope_candidates"] == ["K06"] and not source["rights"] for source in cdc)
    for source in registry["sources"]:
        assert source["status"] == "needs_review"
        assert source["review"] is None and source["automated_acquisition"] == "unknown"
        source_id, url = source["source_id"], source["candidate_url"]
        assert not allows_automated_fetch(registry, source_id, url, user_agent="FixtureBot", at=_AT)
        assert not allows_manual_import(registry, source_id, url, at=_AT)
        assert (
            evaluate_internal_pilot_import(
                registry, source_id, url, document_type=source["document_type"], at=_AT
            )
            == "BLOCKED"
        )


@pytest.fixture
def pilot_registry(registry):
    registry = deepcopy(registry)
    source = _approve(registry)
    source["rights"]["pdf_text"] = {"read": _grant(), "internal_storage": _grant()}
    source["pending_decisions"] = ["robots", "ai_use"]
    return registry


def _pilot(registry, *, source_id="fixture-guide", url=_URL, document_type="pdf", at=_AT):
    return evaluate_internal_pilot_import(
        registry, source_id, url, document_type=document_type, at=at
    )


def test_internal_pilot_manual_approval_does_not_grant_other_use(registry, pilot_registry):
    validate_registry_update(registry, pilot_registry, at=_AT)
    assert _pilot(pilot_registry) == "ELIGIBLE"
    assert not _fetch(pilot_registry)
    for asset in ("original_bytes", "pdf_text"):
        for action in ("reuse", "ai_use", "distribute"):
            assert not _use(pilot_registry, asset, action)


@pytest.mark.parametrize(
    ("asset", "action"),
    [
        ("original_bytes", "read"),
        ("original_bytes", "internal_storage"),
        ("pdf_text", "read"),
        ("pdf_text", "internal_storage"),
    ],
)
def test_internal_pilot_requires_every_read_and_storage_grant(pilot_registry, asset, action):
    source = pilot_registry["sources"][0]
    del source["rights"][asset][action]
    source["rights"]["html_text"] = {"read": _grant(), "internal_storage": _grant()}
    if asset == "pdf_text":
        assert allows_manual_import(pilot_registry, "fixture-guide", _URL, at=_AT)
    assert _pilot(pilot_registry) == "BLOCKED"


@pytest.mark.parametrize("field", ["embedded_assets", "privacy_review", "manual_access"])
def test_internal_pilot_requires_resolved_review(pilot_registry, field):
    source = pilot_registry["sources"][0]
    if field == "embedded_assets":
        source["embedded_assets"] = {"status": "unknown", "evidence_url": None}
    elif field == "privacy_review":
        source["pending_decisions"].append(field)
    else:
        source["terms"]["manual"] = "unknown"
    assert _pilot(pilot_registry) == "BLOCKED"


def test_internal_pilot_requires_evidence_for_text_grant(pilot_registry):
    pilot_registry["sources"][0]["rights"]["pdf_text"]["internal_storage"]["evidence_url"] = None
    assert _pilot(pilot_registry) == "BLOCKED"


def test_internal_pilot_checks_current_review_exact_locator_and_format(pilot_registry):
    assert _pilot(pilot_registry, source_id="fixture-other") == "BLOCKED"
    assert _pilot(pilot_registry, url=_URL + "/") == "BLOCKED"
    assert _pilot(pilot_registry, document_type="html") == "BLOCKED"
    assert _pilot(pilot_registry, at=datetime(2026, 12, 23, tzinfo=UTC)) == "BLOCKED"
    assert _pilot(pilot_registry, at=datetime(2026, 11, 22, tzinfo=UTC)) == "BLOCKED"


def test_internal_pilot_uses_html_text_grants_for_html(pilot_registry):
    url = "https://publisher.example/public-guide.html"
    source = pilot_registry["sources"][0]
    source.update(candidate_url=url, document_type="html")
    assert _pilot(pilot_registry, url=url, document_type="html") == "BLOCKED"
    source["rights"]["html_text"] = source["rights"].pop("pdf_text")
    assert _pilot(pilot_registry, url=url, document_type="html") == "ELIGIBLE"


def test_internal_pilot_requires_manual_status_even_with_automated_approval(registry):
    source = _approve(registry, automated=True)
    source["terms"]["manual"] = "allowed"
    source["rights"]["pdf_text"] = {"read": _grant(), "internal_storage": _grant()}
    assert allows_manual_import(registry, "fixture-guide", _URL, at=_AT)
    assert _pilot(registry) == "BLOCKED"


def test_internal_pilot_approval_cannot_skip_needs_review(registry, pilot_registry):
    registry["sources"][0]["status"] = "candidate"
    with pytest.raises(SourcePolicyError, match="^invalid_approval_transition$"):
        validate_registry_update(registry, pilot_registry, at=_AT)


@pytest.mark.parametrize("version", [None, 0.1, "0.2"])
def test_schema_version(registry, version):
    if version is None:
        del registry["schema_version"]
    else:
        registry["schema_version"] = version
    with pytest.raises(SourcePolicyError, match="^invalid_registry_schema$"):
        validate_registry(registry)
    assert not _fetch(registry)


@pytest.mark.parametrize("field", ["source_id", "candidate_url"])
def test_duplicate_registry_identity(registry, field):
    original = registry["sources"][0]
    duplicate = {
        **original,
        "source_id": "fixture-other",
        "candidate_url": "https://publisher.example/other-guide.pdf",
    }
    duplicate[field] = original[field] if field == "source_id" else original[field] + "/"
    registry["sources"].append(duplicate)
    with pytest.raises(SourcePolicyError, match=f"^duplicate_{field}$"):
        validate_registry(registry)
    assert not _fetch(registry)


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "http://publisher.example/guide",
        "https://other.example/guide",
        "https://publisher..example/guide",
        "https://-publisher.example/guide",
        "https://publisher.example./guide",
        "https://publisher.example:443/guide",
        "https://127.0.0.1/guide",
        "https://records.internal/guide",
        "https://[::1]/guide",
        "https://publisher.example/guide/../private",
        "https://publisher.example/guide//document",
    ],
)
def test_invalid_url_or_host(registry, url):
    source = registry["sources"][0]
    source["candidate_url"] = url
    if url.startswith("https://") and url != "https://other.example/guide":
        source["domain"] = url.split("/")[2]
    with pytest.raises(SourcePolicyError):
        validate_registry(registry)


@pytest.mark.parametrize(
    "locator",
    [
        _URL + "?token=synthetic-test-secret",
        _URL + "#patient-mrn",
        "https://name:synthetic-test-secret@publisher.example/public-guide.pdf",
        "https://publisher.example/patient-synthetic-name/guide",
        "https://publisher.example/mrn-12345/guide",
        "https://publisher.example/guide%2Fsynthetic-test-secret",
        "https://publisher.example/guide/08887766554433221100",
        r"C:\synthetic\patient-record.pdf",
    ],
)
def test_sensitive_locators_are_rejected_without_echo(registry, locator, caplog):
    source = _approve(registry, automated=True)
    assert not _fetch(registry, url=locator)
    source["rights"]["original_bytes"]["read"]["evidence_url"] = locator
    with pytest.raises(SourcePolicyError) as error:
        validate_registry(registry)
    assert locator not in str(error.value)
    assert not _fetch(registry)
    assert not caplog.records


def test_unexpected_locator_field_is_rejected_without_echo(registry):
    registry["sources"][0]["private_locator"] = "synthetic-test-secret"
    with pytest.raises(SourcePolicyError, match="^invalid_registry_schema$"):
        validate_registry(registry)


@pytest.mark.parametrize("status", ["candidate", "needs_review", "rejected"])
def test_unapproved_sources_cannot_fetch_or_use_assets(registry, status):
    source = registry["sources"][0]
    source["status"] = status
    source["rights"]["pdf_text"] = {"reuse": _grant()}
    validate_registry(registry)
    assert not _fetch(registry)
    assert not allows_manual_import(registry, "fixture-guide", _URL, at=_AT)
    assert not _use(registry, "pdf_text", "reuse")
    source["automated_acquisition"] = "allowed"
    with pytest.raises(SourcePolicyError, match="^inconsistent_automated_approval$"):
        validate_registry(registry)


def test_document_and_action_rights_are_independent(registry):
    source = _approve(registry)
    source["rights"]["pdf_text"] = {
        "read": _grant(),
        "reuse": {"status": "unknown", "evidence_url": None},
        "distribute": _grant("restricted"),
        "ai_use": _grant(),
    }
    validate_registry(registry)
    assert allows_manual_import(registry, "fixture-guide", _URL, at=_AT)
    assert not _fetch(registry)
    assert _use(registry, "pdf_text", "read")
    assert not _use(registry, "pdf_text", "internal_storage")
    assert not _use(registry, "pdf_text", "reuse")
    assert not _use(registry, "pdf_text", "distribute")
    assert not _use(registry, "pdf_text", "ai_use")
    source["rights"]["pdf_text"]["reuse"] = _grant()
    assert _use(registry, "pdf_text", "reuse")
    assert _use(registry, "pdf_text", "ai_use")
    for asset in ("images", "external_media", "third_party_assets", "original_bytes"):
        assert not _use(registry, asset, "reuse")
        assert not _use(registry, asset, "distribute")


@pytest.mark.parametrize("status", ["allowed", "restricted", "denied"])
def test_known_rights_require_evidence(registry, status):
    source = _approve(registry, automated=True)
    source["rights"]["pdf_text"] = {"reuse": {"status": status, "evidence_url": None}}
    with pytest.raises(SourcePolicyError, match="^missing_rights_evidence$"):
        validate_registry(registry)
    assert not _fetch(registry)


def test_pdf_text_permission_does_not_allow_storage_of_original(registry):
    source = _approve(registry, automated=True)
    source["rights"]["pdf_text"] = {"read": _grant(), "internal_storage": _grant()}
    source["embedded_assets"] = {"status": "unknown", "evidence_url": None}
    assert not _fetch(registry)
    source["embedded_assets"] = {
        "status": "cleared_for_internal_storage",
        "evidence_url": _COPYRIGHT,
    }
    del source["rights"]["original_bytes"]
    assert not _fetch(registry)


def test_automated_gate_requires_exact_locator_agent_and_current_review(registry):
    source = _approve(registry, automated=True)
    assert _fetch(registry)
    assert not allows_manual_import(registry, "fixture-guide", _URL, at=_AT)
    assert not _fetch(registry, _URL + "/")
    assert not _fetch(registry, "https://publisher.example/other-guide.pdf")
    assert not _fetch(registry, user_agent="OtherBot")
    assert not _fetch(registry, at=datetime(2026, 11, 22, tzinfo=UTC))
    assert not _fetch(registry, at=datetime(2026, 12, 23, tzinfo=UTC))
    assert not _fetch(registry, at=datetime(2026, 11, 24))
    source["terms"]["automated"] = "unknown"
    assert not _fetch(registry)
    source["terms"]["automated"] = "allowed"
    source["robots"]["status"] = "denied"
    assert not _fetch(registry)
    source["robots"]["status"] = "allowed"
    source["robots"]["evidence_url"] = None
    assert not _fetch(registry)


def test_approval_transition_requires_an_explicit_current_review(registry):
    proposed = deepcopy(registry)
    _approve(proposed, automated=True)
    validate_registry_update(registry, proposed, at=_AT)
    with pytest.raises(SourcePolicyError, match="^approval_requires_current_review$"):
        validate_registry_update(registry, proposed, at=datetime(2026, 12, 23, tzinfo=UTC))
    for old_status in ("candidate", "rejected"):
        registry["sources"][0]["status"] = old_status
        with pytest.raises(SourcePolicyError, match="^invalid_approval_transition$"):
            validate_registry_update(registry, proposed, at=_AT)
    with pytest.raises(SourcePolicyError, match="^new_source_requires_review$"):
        validate_registry_update({"schema_version": "0.1", "sources": []}, proposed, at=_AT)


def test_changed_approval_must_return_to_review(registry):
    _approve(registry)
    proposed = deepcopy(registry)
    source = proposed["sources"][0]
    source["rights"]["pdf_text"] = {"distribute": _grant()}
    with pytest.raises(SourcePolicyError, match="^approval_requires_new_review$"):
        validate_registry_update(registry, proposed, at=_AT)

    source["status"] = "needs_review"
    validate_registry_update(registry, proposed, at=_AT)
    with pytest.raises(SourcePolicyError, match="^approval_requires_current_review$"):
        validate_registry_update(proposed, registry, at=_AT)
    approved = deepcopy(registry)
    _approve(approved, automated=True)["review"]["reviewed_at"] = "2026-11-24T00:00:00Z"
    validate_registry_update(proposed, approved, at=_AT)
