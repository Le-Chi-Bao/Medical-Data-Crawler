"""Operator CLI. No command performs network I/O without --enable-live."""

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .discovery import DiscoveryError
from .multisource import SOURCES
from .operation_policy import OperationGrant, OperationPolicyGate, OperatorPolicyAuthority
from .pmc import candidates, run, scope
from .pmc_transport import PMCTransport
from .pmc_verification import verify_corpus

OPERATIONS = ("fetch_document", "retain_metadata", "store_original", "extract_content")


def read_approval(path):
    if path.stat().st_size > 65536:
        raise DiscoveryError("invalid_approval")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = candidates(value["pmcids"])
    if any(
        value.get(key) is not True
        for key in (
            "approved",
            "exclusive_provider_ip",
            "source_terms_reviewed",
            "skin_scope_reviewed",
        )
    ):
        raise DiscoveryError("permission_denied")
    if any(op not in OPERATIONS for op in value["operations"]):
        raise DiscoveryError("invalid_operations")
    if not isinstance(value.get("rights"), dict) or not isinstance(value.get("output"), str):
        raise DiscoveryError("invalid_approval")
    for pmcid in ids:
        review = value["rights"].get(pmcid, {})
        if not isinstance(review, dict) or not all(
            isinstance(review.get(key), str) and review[key].strip()
            for key in ("license_uri", "evidence")
        ):
            raise DiscoveryError("rights_not_established")
        if (
            review.get("retain_original") is not True
            or review.get("third_party_reviewed") is not True
        ):
            raise DiscoveryError("rights_not_established")
    start = datetime.fromisoformat(value["valid_from"])
    end = datetime.fromisoformat(value["valid_until"])
    grants = tuple(
        OperationGrant(pmcid + ":" + op, scope(pmcid, op), start, end)
        for pmcid in ids
        for op in value["operations"]
        if op in OPERATIONS
    )
    gate = OperationPolicyGate(OperatorPolicyAuthority(grants))
    for pmcid in ids:
        for op in ("fetch_document", "retain_metadata", "store_original"):
            gate.require(pmcid + ":" + op, scope(pmcid, op), datetime.now(UTC))
    return value, gate


class FileGate:
    """Re-read operator-owned approval at every boundary, including revocation."""

    def __init__(self, path, initial):
        self.path, self.initial = path, initial

    def require(self, grant_id, requested_scope, at):
        try:
            value, gate = read_approval(self.path)
        except (OSError, ValueError, KeyError, TypeError):
            raise DiscoveryError("approval_unavailable") from None
        if value != self.initial:
            raise DiscoveryError("approval_changed")
        gate.require(grant_id, requested_scope, at)


def demo(output):
    # Synthetic fixture is embedded so installed CLI does not depend on tests/.
    from .pmc_demo import FIXTURE

    class Replay:
        is_live = False

        def fetch(self, pmcid, authorize):
            authorize()
            return FIXTURE

    now = datetime.now(UTC)
    grants = tuple(
        OperationGrant(
            "PMC1:" + op, scope("PMC1", op), now - timedelta(minutes=1), now + timedelta(hours=1)
        )
        for op in OPERATIONS
    )
    rights = {
        "PMC1": {
            "license_uri": "https://creativecommons.org/licenses/by/4.0/",
            "retain_original": True,
            "extract_text": True,
            "third_party_reviewed": True,
            "evidence": "synthetic-demo-only",
        }
    }
    return run(
        ["PMC1"],
        transport=Replay(),
        gate=OperationPolicyGate(OperatorPolicyAuthority(grants)),
        rights=rights,
        output=output,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sources")
    pmc = commands.add_parser("pmc")
    pmc.add_argument(
        "action", choices=["capabilities", "prepare", "validate", "demo", "pilot", "verify"]
    )
    pmc.add_argument("--pmcid", nargs="+")
    pmc.add_argument("--approval", type=Path)
    pmc.add_argument("--output", type=Path, default=Path("data/pmc-demo"))
    pmc.add_argument("--enable-live", action="store_true")
    report = commands.add_parser("report")
    report.add_argument("--output", type=Path, default=Path("data/pmc-demo"))
    args = parser.parse_args(argv)
    try:
        if args.command == "sources":
            result = [s.to_dict() for s in SOURCES.values()]
        elif args.command == "report":
            result = [
                json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(args.output.glob("runs/*/report.json"))
            ]
        elif args.action == "capabilities":
            result = SOURCES["pmc"].to_dict()
        elif args.action == "verify":
            result = verify_corpus(args.output)
        elif args.action == "prepare":
            result = {
                "approved": False,
                "pmcids": candidates(args.pmcid),
                "operations": list(OPERATIONS),
                "valid_from": "",
                "valid_until": "",
                "output": "data/pmc-live",
                "exclusive_provider_ip": False,
                "source_terms_reviewed": False,
                "skin_scope_reviewed": False,
                "rights": {},
                "note": "Review skin-lesion relevance and rights for EACH PMCID",
            }
        elif args.action == "demo":
            result, folder = demo(args.output)
            result["run_directory"] = str(folder)
        else:
            if args.approval is None:
                raise DiscoveryError("approval_required")
            value, _ = read_approval(args.approval)
            if args.action == "validate":
                result = {
                    "status": "configuration_valid",
                    "network_requests": 0,
                    "note": "Rights evidence still requires operator review",
                }
            else:
                if not args.enable_live:
                    raise DiscoveryError("network_disabled")
                # One attempt per exact approval, including unsuccessful pilots.
                destination = Path(value["output"])
                destination.mkdir(parents=True, exist_ok=True)
                fingerprint = hashlib.sha256(
                    json.dumps(value, sort_keys=True).encode("utf-8")
                ).hexdigest()
                marker = destination / ("pilot-attempt-" + fingerprint)
                try:
                    with marker.open("x", encoding="utf-8") as stream:
                        stream.write(datetime.now(UTC).isoformat())
                except FileExistsError:
                    raise DiscoveryError("renewed_approval_required") from None
                result, folder = run(
                    value["pmcids"],
                    transport=PMCTransport(enabled=True, exclusive_provider_ip=True),
                    gate=FileGate(args.approval, value),
                    rights=value["rights"],
                    output=Path(value["output"]),
                )
                result["run_directory"] = str(folder)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (DiscoveryError, ValueError, KeyError, TypeError, OSError) as error:
        print(
            json.dumps(
                {
                    "error": error.code
                    if isinstance(error, DiscoveryError)
                    else "invalid_configuration"
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
