import pytest

from medical_data_crawler.internal_import import (
    IntakeError,
    InternalIntakeGateway,
    parse_authorizations,
)


@pytest.fixture
def intake_contract(tmp_path):
    root = tmp_path / "operating"
    root.mkdir()
    document = {
        "source_id": "internal-fixture",
        "logical_key": "synthetic-document",
        "locator": "internal:document-reference",
        "local_path": str(root / "synthetic.html"),
        "format": "html",
        "provider_ref": "provider-fixture",
        "authorization_ref": "approval-fixture",
        "allow_store": True,
        "allow_extract": True,
        "access_basis": "internal_authorization",
    }
    grant = dict(
        document,
        active=True,
        expires_at="2099-01-01T00:00:00Z",
        operation="internal_import",
        allow_read=True,
    )
    return root, document, grant


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"intake_version": 0.1, "documents": []},
        {"intake_version": "0.1", "documents": {}},
        {"intake_version": "0.1", "documents": [], "authorizations": []},
    ],
)
def test_invalid_intake_envelope_uses_safe_config_error(intake_contract, tmp_path, payload):
    root, _, grant = intake_contract
    state = tmp_path / "state"
    gateway = InternalIntakeGateway(
        approved_roots=(root,),
        state_root=state,
        authorizations=parse_authorizations(
            {"authorization_version": "0.1", "authorizations": [grant]}
        ),
    )
    with pytest.raises(IntakeError) as error:
        gateway.run(payload)
    assert error.value.code == "invalid_intake_spec"
    assert not state.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"source_id": "SOURCE/SECRET_VALUE"},
        {"logical_key": "../../SECRET_VALUE"},
        {"locator": "internal:fixture?token=SECRET_VALUE"},
        {"provider_ref": "Provider SECRET_VALUE"},
        {"allow_store": 1},
        {"allow_extract": "true"},
        {"format": "docx"},
        {"expected_sha256": "x" * 64},
        {"reuse": "allowed"},
        {"active": True, "allow_read": True},
        {"access_basis": "SECRET VALUE"},
    ],
)
def test_invalid_document_is_safely_reported_and_does_not_block_batch(
    intake_contract, tmp_path, changes
):
    root, document, grant = intake_contract
    (root / "synthetic.html").write_bytes(b"<p>Synthetic fixture</p>")
    gateway = InternalIntakeGateway(
        approved_roots=(root,),
        state_root=tmp_path / "state",
        authorizations=parse_authorizations(
            {"authorization_version": "0.1", "authorizations": [grant]}
        ),
    )
    result = gateway.run(
        {"intake_version": "0.1", "documents": [dict(document, **changes), document]},
        dry_run=True,
    )
    assert result.report["items"][0]["code"] == "invalid_document_spec"
    assert result.report["items"][0]["document_id"] is None
    assert result.report["items"][1]["status"] == "validated"
    assert "SECRET" not in repr(result.report)


@pytest.mark.parametrize(
    "changes",
    [
        {"active": "true"},
        {"allow_read": 1},
        {"expires_at": "2099-01-01T00:00:00"},
        {"expires_at": "2099-13-01T00:00:00Z"},
        {"unexpected_identity": "SECRET_VALUE"},
    ],
)
def test_invalid_trusted_authorization_config_uses_safe_error(intake_contract, changes):
    _, _, grant = intake_contract
    with pytest.raises(IntakeError) as error:
        parse_authorizations(
            {"authorization_version": "0.1", "authorizations": [dict(grant, **changes)]}
        )
    assert error.value.code == "invalid_authorization_config"
    assert "SECRET" not in str(error.value)


def test_duplicate_or_missing_authorization_fields_are_rejected(intake_contract):
    _, _, grant = intake_contract
    incomplete = {key: value for key, value in grant.items() if key != "allow_read"}
    for grants in ([grant, grant], [incomplete]):
        with pytest.raises(IntakeError) as error:
            parse_authorizations({"authorization_version": "0.1", "authorizations": grants})
        assert error.value.code == "invalid_authorization_config"
