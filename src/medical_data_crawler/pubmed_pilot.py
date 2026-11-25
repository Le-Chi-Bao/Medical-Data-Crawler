"""Bounded metadata-only pilot; operator approvals stay outside request input."""

import json
import os
import secrets
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from .api_transport import APISettings, SecureMetadataTransport
from .catalog import AccessDomain, Catalog, Rendition
from .catalog.discovery import CatalogDiscoveryWriter
from .catalog.model import validate_id
from .discovery import (
    ALLOWED_FIELDS,
    DiscoveryError,
    DiscoveryPermit,
    DiscoveryRequest,
    SearchSnapshot,
)
from .internal_import_cli import _CLIError, _read_json
from .operation_policy import (
    OperationGrant,
    OperationPolicyGate,
    OperatorPolicyAuthority,
    discovery_scope,
)
from .pubmed import PubMedDiscoveryConnector, capture_live_snapshot

# Reviewable application profiles, not source approval changes or full-text grants.
SEARCH_PROFILES = {
    "melanoma-v1": '"Melanoma"[MeSH Terms] AND "skin"[Title/Abstract]',
    "skin-lesions-v1": '"Skin Neoplasms"[MeSH Terms] AND "Diagnosis, Differential"[MeSH Terms]',
}
METADATA_OPERATIONS = ("discover_metadata", "retain_metadata")


def _authority(permit):
    return OperatorPolicyAuthority(
        tuple(
            OperationGrant(
                permit.id + ":" + operation,
                discovery_scope(permit, operation),
                permit.valid_from,
                permit.valid_until,
            )
            for operation in METADATA_OPERATIONS
        )
    )


def read_operator_approval(path: Path):
    """Read a trusted local file afresh; no credentials or request-created grants."""
    try:
        value = _read_json(path, "approval_unavailable")
        keys = {
            "approval_id",
            "domain_id",
            "profile_id",
            "approved_query",
            "fields",
            "valid_from",
            "valid_until",
            "operations",
            "revoked",
            "source_terms_reviewed",
            "network_approved",
            "exclusive_provider_ip",
            "output_dir",
        }
        if type(value) is not dict or set(value) != keys:
            raise ValueError
        if (
            value["profile_id"] not in SEARCH_PROFILES
            or value["approved_query"] != SEARCH_PROFILES[value["profile_id"]]
            or value["source_terms_reviewed"] is not True
            or value["network_approved"] is not True
            or value["exclusive_provider_ip"] is not True
            or value["operations"] != list(METADATA_OPERATIONS)
            or type(value["revoked"]) is not bool
            or type(value["fields"]) is not list
            or not all(type(f) is str for f in value["fields"])
            or len(set(value["fields"])) != len(value["fields"])
            or not {"pmid"} <= set(value["fields"]) <= ALLOWED_FIELDS
            or type(value["output_dir"]) is not str
            or not value["output_dir"].strip()
        ):
            raise ValueError
        validate_id(value["approval_id"])
        validate_id(value["domain_id"])
        permit = DiscoveryPermit(
            value["approval_id"],
            value["domain_id"],
            value["profile_id"],
            value["approved_query"],
            datetime.fromisoformat(value["valid_from"]),
            datetime.fromisoformat(value["valid_until"]),
            fields=frozenset(value["fields"]),
            allow_discovery=True,
            allow_retention=True,
        )
        authority = _authority(permit)
        if value["revoked"]:
            for operation in METADATA_OPERATIONS:
                authority.revoke(permit.id + ":" + operation)
        output = Path(value["output_dir"]).absolute()
        return permit, authority, output
    except (ValueError, TypeError, KeyError, _CLIError, OSError):
        raise DiscoveryError("invalid_operator_approval") from None


class FileDecisionProvider:
    """Reread independent operator config at every use, including pre-commit.

    A changed approval/output destination fails closed until a new invocation.
    File ACLs and atomic updates are the operator's trust boundary.
    """

    def __init__(self, path: Path):
        self.path = path.absolute()
        self.permit, _, self.output = read_operator_approval(self.path)

    def require(self, grant_id, scope, at):
        permit, authority, output = read_operator_approval(self.path)
        if permit.fingerprint != self.permit.fingerprint or output != self.output:
            raise DiscoveryError("permission_denied")
        authority.require(grant_id, scope, at)


def operator_transport(approval: Path, *, enable_network=False):
    provider = FileDecisionProvider(approval)
    permit, output = provider.permit, provider.output
    gate = OperationPolicyGate(provider)
    gate.discovery(permit, datetime.now(UTC))
    transport = SecureMetadataTransport(
        permit,
        gate,
        settings=APISettings(
            enabled=enable_network,
            exclusive_provider_ip=True,
            email=os.environ.get("MDC_NCBI_EMAIL"),
            api_key=os.environ.get("MDC_NCBI_API_KEY"),
        ),
    )
    return permit, output, transport


def _save(path, value):
    # Replace checkpoints only; pinned snapshot and signing key are never rewritten.
    temporary = path.with_suffix(".pending")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_pilot(
    output: Path,
    run_id: str,
    permit,
    transport,
    *,
    limit=20,
    resume=False,
    page_size=20,
    clock=lambda: datetime.now(UTC),
):
    validate_id(run_id)
    if type(limit) is not int or not 1 <= limit <= 50:
        raise DiscoveryError("invalid_request")
    request = DiscoveryRequest(
        permit.domain_id, permit.profile_id, permit.query, page_size=page_size
    )
    transport.authorize(permit)
    run_dir = output / "runs" / run_id
    if resume:
        try:
            state = _read_json(run_dir / "checkpoint.json", "invalid_checkpoint")
            raw = _read_json(run_dir / "snapshot.json", "invalid_snapshot")
            snapshot = SearchSnapshot(**{**raw, "pmids": tuple(raw["pmids"])})
            with (run_dir / "cursor.key").open("rb") as stream:
                key = stream.read(33)
            if (
                type(state) is not dict
                or set(state) != {"snapshot", "permit", "cursor", "complete", "page_size", "known"}
                or type(state["complete"]) is not bool
                or type(state["known"]) is not int
                or not 0 <= state["known"] <= len(snapshot.pmids)
                or state["cursor"] is not None
                and (type(state["cursor"]) is not str or len(state["cursor"]) > 80)
                or state["complete"]
                and state["cursor"] is not None
                or len(key) != 32
                or state["snapshot"] != snapshot.fingerprint
                or state["permit"] != permit.fingerprint
                or state["page_size"] != page_size
                or snapshot.sort != "provider-pub-date"
                or snapshot.profile_id != permit.profile_id
                or snapshot.query != permit.query
            ):
                raise ValueError
        except (OSError, _CLIError, ValueError, KeyError, TypeError):
            raise DiscoveryError("invalid_checkpoint") from None
    else:
        # Refuse accidentally replacing a prior run, before any network I/O.
        if run_dir.exists():
            raise DiscoveryError("run_exists")
        snapshot = capture_live_snapshot(request, permit, transport, limit=limit, clock=clock)
        run_dir.mkdir(parents=True, exist_ok=False)
        key = secrets.token_bytes(32)
        with (run_dir / "cursor.key").open("xb") as stream:
            stream.write(key)
        with (run_dir / "snapshot.json").open("x", encoding="utf-8") as stream:
            json.dump(asdict(snapshot), stream, indent=2)
        state = {
            "snapshot": snapshot.fingerprint,
            "permit": permit.fingerprint,
            "cursor": None,
            "complete": False,
            "page_size": page_size,
            "known": None,
        }
    connector = PubMedDiscoveryConnector(snapshot, cursor_key=key, transport=transport, clock=clock)
    connector.authorize(request, permit)
    with Catalog(output / "catalog") as catalog:
        catalog.create_domain(AccessDomain(permit.domain_id))
        scope = catalog.domain(permit.domain_id)
        if state["known"] is None:
            state["known"] = sum(
                scope.find_source_item("pubmed", p) is not None for p in snapshot.pmids
            )
        _save(run_dir / "checkpoint.json", state)
        writer = CatalogDiscoveryWriter(scope, connector)
        issues = []
        # Each page has at most 50 items. A failed page retains its old cursor.
        while not state["complete"]:
            outcome = writer.run(replace(request, cursor=state["cursor"]), permit)
            issues = [asdict(i) for i in outcome.report.issues]
            if outcome.report.status in {"failed", "incomplete"}:
                break
            state["cursor"] = outcome.next_cursor
            state["complete"] = outcome.report.status == "complete"
            _save(run_dir / "checkpoint.json", state)
        retained = sum(scope.find_source_item("pubmed", p) is not None for p in snapshot.pmids)
        catalog.verify()
        result = {
            "report_version": "0.1",
            "run_id": run_id,
            "status": "complete" if state["complete"] else "incomplete",
            "provider_total": snapshot.total_results,
            "found": len(snapshot.pmids),
            "limited": snapshot.total_results > len(snapshot.pmids),
            "accepted": retained - state["known"],
            "already_known": state["known"],
            "rejected": len(snapshot.pmids) - retained,
            "issues": issues,
            "integrity": "pass",
            "full_text_downloads": 0,
            "renditions": len(scope.list(Rendition)),
            "network_mode": "live" if transport.is_live else "simulated",
        }
    _save(run_dir / "report.json", result)
    return result
