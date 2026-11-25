"""Operator-owned decisions, separate from submitted requests and legacy approvals."""

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Protocol

from .discovery import DiscoveryError, DiscoveryPermit, valid_time

OPERATIONS = frozenset(
    {
        "discover_metadata",
        "retain_metadata",
        "fetch_document",
        "store_original",
        "extract_content",
        "export_data",
        "ai_use",
    }
)


@dataclass(frozen=True, slots=True)
class OperationScope:
    domain_id: str
    source: str
    operation: str
    purpose: str
    resource_id: str
    profile_id: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class OperationGrant:
    id: str
    scope: OperationScope
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self):
        if (
            type(self.scope) is not OperationScope
            or self.scope.operation not in OPERATIONS
            or not all(
                type(v) is str and v and len(v) <= 256
                for v in (
                    self.id,
                    self.scope.domain_id,
                    self.scope.source,
                    self.scope.purpose,
                    self.scope.resource_id,
                    self.scope.profile_id,
                    self.scope.policy_version,
                )
            )
            or not all(valid_time(t) for t in (self.valid_from, self.valid_until))
            or self.valid_until <= self.valid_from
        ):
            raise DiscoveryError("invalid_configuration")


class DecisionProvider(Protocol):
    def require(self, grant_id: str, scope: OperationScope, at: datetime) -> None: ...


class OperatorPolicyAuthority:
    """Trusted local configuration. No request-facing grant creation interface.

    A long-running deployment must inject a durable decision provider instead.
    Revocations are monotonic for the life of this authority.
    """

    def __init__(self, grants: tuple[OperationGrant, ...] = ()):
        if len({g.id for g in grants}) != len(grants):
            raise DiscoveryError("invalid_configuration")
        self._grants = {g.id: g for g in grants}
        self._revoked: set[str] = set()
        self._lock = RLock()

    def revoke(self, grant_id: str) -> None:
        with self._lock:
            self._revoked.add(grant_id)

    def require(self, grant_id: str, scope: OperationScope, at: datetime) -> None:
        with self._lock:
            grant = self._grants.get(grant_id)
            if grant is None or grant.scope != scope or scope.operation not in OPERATIONS:
                raise DiscoveryError("permission_denied")
            if grant_id in self._revoked:
                raise DiscoveryError("permission_revoked")
            if not valid_time(at) or not grant.valid_from <= at < grant.valid_until:
                raise DiscoveryError("permission_expired")


def discovery_scope(permit: DiscoveryPermit, operation="discover_metadata") -> OperationScope:
    return OperationScope(
        permit.domain_id,
        permit.source,
        operation,
        permit.retention_purpose,
        permit.fingerprint,
        permit.profile_id,
        permit.field_policy_version,
    )


class OperationPolicyGate:
    def __init__(self, provider: DecisionProvider):
        self._provider = provider

    def require(self, grant_id: str, scope: OperationScope, at: datetime) -> None:
        try:
            self._provider.require(grant_id, scope, at)
        except DiscoveryError as error:
            if error.code in {"permission_denied", "permission_revoked", "permission_expired"}:
                raise DiscoveryError(error.code) from None
            raise DiscoveryError("policy_unavailable") from None
        except Exception:
            raise DiscoveryError("policy_unavailable") from None

    def discovery(self, permit: DiscoveryPermit, at: datetime) -> None:
        # Retention is separate; neither decision implies any full-text or AI right.
        for operation in ("discover_metadata", "retain_metadata"):
            self.require(permit.id + ":" + operation, discovery_scope(permit, operation), at)
