from dataclasses import replace
from datetime import timedelta

import pytest

from medical_data_crawler.discovery import DiscoveryError
from medical_data_crawler.operation_policy import OperationPolicyGate, discovery_scope
from medical_data_crawler.secure_api_demo import NOW, demo_transport


@pytest.mark.parametrize(
    "operation",
    [
        "fetch_document",
        "store_original",
        "extract_content",
        "export_data",
        "ai_use",
        "unknown",
    ],
)
def test_discovery_cannot_authorize_other_operations(operation):
    permit, authority, _, _ = demo_transport()
    gate = OperationPolicyGate(authority)
    with pytest.raises(DiscoveryError, match="^permission_denied$"):
        gate.require(permit.id + ":discover_metadata", discovery_scope(permit, operation), NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"domain_id": "wrong"},
        {"source": "pmc"},
        {"purpose": "ai"},
        {"resource_id": "different-query-or-fields"},
        {"profile_id": "other"},
        {"policy_version": "v999"},
    ],
)
def test_all_scope_bindings_are_required(changes):
    permit, authority, _, _ = demo_transport()
    with pytest.raises(DiscoveryError, match="^permission_denied$"):
        authority.require(
            permit.id + ":discover_metadata", replace(discovery_scope(permit), **changes), NOW
        )


def test_no_self_authorization_expiry_revocation_and_retention_are_independent():
    permit, authority, _, transport = demo_transport()
    with pytest.raises(DiscoveryError, match="^permission_denied$"):
        transport.authorize(replace(permit, id="self-issued"))
    for at in (permit.valid_from - timedelta(seconds=1), permit.valid_until):
        with pytest.raises(DiscoveryError, match="^permission_expired$"):
            authority.require(permit.id + ":discover_metadata", discovery_scope(permit), at)
    authority.revoke(permit.id + ":retain_metadata")
    # Discovery alone stays valid, but cannot pass the metadata storage gate.
    authority.require(permit.id + ":discover_metadata", discovery_scope(permit), NOW)
    with pytest.raises(DiscoveryError, match="^permission_revoked$"):
        transport.authorize()


def test_unavailable_authority_fails_closed_without_exception_leak():
    class Failing:
        def require(self, *args):
            raise RuntimeError("PRIVATE_TOKEN")

    permit, _, _, _ = demo_transport()
    with pytest.raises(DiscoveryError, match="^policy_unavailable$"):
        OperationPolicyGate(Failing()).discovery(permit, NOW)
