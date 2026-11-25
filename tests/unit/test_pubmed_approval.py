"""Synthetic local approvals only; the suite's socket/DNS guard applies."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from medical_data_crawler.discovery import DiscoveryError
from medical_data_crawler.pubmed_approval import validate_approval
from medical_data_crawler.pubmed_cli import main
from medical_data_crawler.pubmed_pilot import SEARCH_PROFILES, operator_transport

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)


@pytest.fixture
def approval(tmp_path):
    path = tmp_path / "approval.json"
    value = {
        "approval_id": "operator-test",
        "domain_id": "public-medical-metadata",
        "profile_id": "melanoma-v1",
        "approved_query": SEARCH_PROFILES["melanoma-v1"],
        "fields": ["pmid", "title"],
        "valid_from": "2026-11-25T00:00:00+00:00",
        "valid_until": "2026-11-26T00:00:00+00:00",
        "operations": ["discover_metadata", "retain_metadata"],
        "revoked": False,
        "source_terms_reviewed": True,
        "network_approved": True,
        "exclusive_provider_ip": True,
        "output_dir": str(tmp_path / "new" / "output"),
    }
    return path, value


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize(
    "changes,code,status",
    [
        ({"approval_id": "secret invalid id"}, "invalid_identifier", "invalid_configuration"),
        ({"domain_id": []}, "invalid_identifier", "invalid_configuration"),
        ({"profile_id": []}, "invalid_profile", "invalid_configuration"),
        ({"profile_id": "unknown"}, "invalid_profile", "invalid_configuration"),
        ({"approved_query": "SECRET"}, "query_binding_mismatch", "invalid_configuration"),
        ({"fields": ["title"]}, "invalid_fields", "invalid_configuration"),
        ({"fields": ["pmid", "abstract"]}, "invalid_fields", "invalid_configuration"),
        ({"fields": ["pmid", "pmid"]}, "invalid_fields", "invalid_configuration"),
        ({"fields": ["pmid", {}]}, "invalid_fields", "invalid_configuration"),
        ({"fields": "pmid"}, "invalid_fields", "invalid_configuration"),
        ({"operations": ["discover_metadata"]}, "invalid_operations", "invalid_configuration"),
        ({"valid_from": "2026-11-25"}, "invalid_validity_interval", "invalid_configuration"),
        ({"valid_from": None}, "invalid_validity_interval", "invalid_configuration"),
        ({"valid_until": "bad"}, "invalid_validity_interval", "invalid_configuration"),
        (
            {"valid_until": "2026-11-25T00:00:00Z"},
            "invalid_validity_interval",
            "invalid_configuration",
        ),
        (
            {"valid_from": "2026-11-24T00:00:00Z", "valid_until": NOW.isoformat()},
            "approval_expired",
            "not_authorized",
        ),
        ({"valid_from": "2026-11-25T13:00:00Z"}, "approval_not_yet_valid", "not_authorized"),
        ({"revoked": True}, "permission_revoked", "not_authorized"),
        ({"source_terms_reviewed": False}, "source_terms_not_reviewed", "not_authorized"),
        ({"network_approved": False}, "network_not_approved", "not_authorized"),
        ({"exclusive_provider_ip": False}, "shared_ip_uncoordinated", "not_authorized"),
        ({"network_approved": "true"}, "invalid_boolean", "invalid_configuration"),
        ({"revoked": 0}, "invalid_boolean", "invalid_configuration"),
        ({"output_dir": ""}, "invalid_output_directory", "invalid_configuration"),
        ({"output_dir": "bad\u0000path"}, "invalid_output_directory", "invalid_configuration"),
        ({"output_dir": "NUL"}, "invalid_output_directory", "invalid_configuration"),
        ({"output_dir": r"\\remote\share"}, "invalid_output_directory", "invalid_configuration"),
        ({"output_dir": "C:relative"}, "invalid_output_directory", "invalid_configuration"),
    ],
)
def test_diagnostic_outcomes(approval, changes, code, status):
    path, value = approval
    write(path, {**value, **changes})
    before = path.read_bytes()
    result = validate_approval(path, at=NOW)
    assert result["status"] == status
    assert code in [issue["code"] for issue in result["issues"]]
    assert result["network_enabled"] is False
    assert result["ready_for_explicit_live_pilot"] is False
    assert "SECRET" not in json.dumps(result)
    assert path.read_bytes() == before


@pytest.mark.parametrize("raw", ["{", "[]", '{"a":1,"a":2}', '{"a":NaN}', "\ufeff{}"])
def test_malformed_json_and_schema(approval, raw):
    path, _ = approval
    path.write_text(raw, encoding="utf-8")
    assert validate_approval(path, at=NOW)["status"] == "invalid_configuration"


def test_missing_keys_and_unexpected_keys_are_sanitized(approval):
    path, value = approval
    del value["fields"]
    value["SECRET_KEY"] = "SECRET_VALUE"
    write(path, value)
    result = validate_approval(path, at=NOW)
    assert result["issues"] == [
        {"code": "missing_keys", "keys": ["fields"]},
        {"code": "unexpected_keys"},
    ]
    assert "SECRET" not in json.dumps(result)


def test_missing_file_and_output_is_file(approval):
    path, value = approval
    assert validate_approval(path)["issues"] == [{"code": "approval_missing"}]
    value["output_dir"] = str(path / "child")
    write(path, value)
    assert {"code": "invalid_output_directory"} in validate_approval(path, at=NOW)["issues"]


def test_ready_is_read_only_and_matches_actual_reader(approval):
    path, value = approval
    # Inclusive start, explicit offset, and UTC equivalent are supported.
    value["valid_from"] = "2026-11-25T19:00:00+07:00"
    write(path, value)
    result = validate_approval(path, at=NOW)
    assert result["status"] == "ready" and result["issues"] == []
    assert result["configuration_valid"] and result["ready_for_explicit_live_pilot"]
    assert not (path.parent / "new").exists()
    assert not operator_transport(path)[2].settings.enabled


def test_all_operator_flags_reported_and_live_gate_still_blocks(approval):
    path, value = approval
    for flag in ("source_terms_reviewed", "network_approved", "exclusive_provider_ip"):
        value[flag] = False
    write(path, value)
    assert len(validate_approval(path, at=NOW)["issues"]) == 3
    with pytest.raises(DiscoveryError, match="invalid_operator_approval"):
        operator_transport(path, enable_network=True)


def test_validation_cli_exit_codes_and_never_constructs_transport(approval, monkeypatch, capsys):
    def blocked(*args, **kwargs):
        raise AssertionError("Validation must not construct a transport")

    monkeypatch.setattr("medical_data_crawler.pubmed_cli.operator_transport", blocked)
    path, value = approval
    argv = ["validate-approval", "--approval", str(path)]
    assert main(argv) == 2
    assert json.loads(capsys.readouterr().out)["issues"] == [{"code": "approval_missing"}]
    value["valid_from"] = "2020-01-01T00:00:00Z"
    value["valid_until"] = "2099-01-01T00:00:00Z"
    value["network_approved"] = False
    write(path, value)
    assert main(argv) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "not_authorized"
    value["network_approved"] = True
    write(path, value)
    assert main(argv) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"


def test_public_template_is_valid_but_never_authorizes_live(approval):
    path, _ = approval
    template = Path(__file__).resolve().parents[2] / "examples/pubmed-approval.example.json"
    value = json.loads(template.read_text(encoding="utf-8"))
    write(path, value)
    result = validate_approval(path, at=NOW)
    assert result["configuration_valid"] and result["status"] == "not_authorized"
    assert {i["code"] for i in result["issues"]} == {
        "source_terms_not_reviewed",
        "network_not_approved",
        "shared_ip_uncoordinated",
    }
    with pytest.raises(DiscoveryError, match="invalid_operator_approval"):
        operator_transport(path, enable_network=True)


def test_unavailable_and_changed_configuration_fail_closed(approval, monkeypatch):
    path, value = approval

    def unavailable(*args, **kwargs):
        raise PermissionError

    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", unavailable)
        assert validate_approval(path)["issues"] == [{"code": "approval_unavailable"}]
    write(path, value)

    def changed(*args):
        raise DiscoveryError("invalid_operator_approval")

    monkeypatch.setattr("medical_data_crawler.pubmed_approval.read_operator_approval", changed)
    assert validate_approval(path, at=NOW)["issues"] == [{"code": "approval_changed_or_invalid"}]


def test_cli_demo_twice_writes_identical_metadata_without_network(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    reports = []
    for _ in range(2):
        assert main(["demo"]) == 0
        reports.append(json.loads(capsys.readouterr().out))
    assert reports[0] == reports[1]
    assert reports[0]["documents"] == 2 and reports[0]["observations"] == 16
    assert reports[0]["network_requests"] == reports[0]["full_text_downloads"] == 0
    assert reports[0]["integrity"] == "pass" and reports[0]["renditions"] == 0
    saved = tmp_path / "data/secure-api-demo/report.json"
    assert json.loads(saved.read_text()) == reports[0]
