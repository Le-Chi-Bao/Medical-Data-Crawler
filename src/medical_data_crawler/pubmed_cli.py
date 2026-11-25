"""Pilot PubMed chỉ lấy metadata; mặc định không kết nối Internet."""

import json
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

from .catalog import Catalog, Document, Observation
from .catalog.model import CatalogError, validate_id
from .discovery import DiscoveryError
from .internal_import_cli import _ArgumentParser, _CLIError, _read_json
from .pubmed_approval import validate_approval
from .pubmed_pilot import SEARCH_PROFILES, operator_transport, run_pilot


def main(argv=None):
    parser = _ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("profiles", help="Xem các query da liễu có sẵn")
    preview = commands.add_parser("preview", help="Xem kế hoạch, không gọi mạng")
    preview.add_argument("--profile", choices=SEARCH_PROFILES, default="melanoma-v1")
    preview.add_argument("--limit", type=int, default=20)
    commands.add_parser("demo", help="Chạy dữ liệu tổng hợp, không gọi mạng")
    validation = commands.add_parser("validate-approval", help="Kiểm tra phê duyệt, không gọi mạng")
    validation.add_argument("--approval", type=Path, required=True)
    for name in ("pilot", "report", "inspect"):
        sub = commands.add_parser(name)
        sub.add_argument("--approval", type=Path, required=True, help="File phê duyệt của operator")
        if name == "pilot":
            sub.add_argument("--enable-network", action="store_true", help="Chủ động bật Internet")
            sub.add_argument("--limit", type=int, default=20)
            sub.add_argument("--resume", help="Tiếp tục run ID đã ghim, không chạy lại ESearch")
        if name == "report":
            sub.add_argument("--run-id", required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == "profiles":
            result = {"profiles": SEARCH_PROFILES, "network_enabled": False}
        elif args.command == "preview":
            if not 1 <= args.limit <= 50:
                raise DiscoveryError("invalid_request")
            result = {
                "profile": args.profile,
                "query": SEARCH_PROFILES[args.profile],
                "limit": args.limit,
                "workers": 1,
                "requests_per_second": 3,
                "api_key_required": False,
                "network_enabled": False,
                "full_text_downloads": 0,
                "approval_required": True,
            }
        elif args.command == "validate-approval":
            result = validate_approval(args.approval)
        elif args.command == "demo":
            from .secure_api_demo import run_demo

            result = run_demo()
        else:
            permit, output, transport = operator_transport(
                args.approval,
                enable_network=getattr(args, "enable_network", False),
            )
            if args.command == "pilot":
                if not args.enable_network:
                    raise DiscoveryError("network_disabled")
                result = run_pilot(
                    output,
                    args.resume or "pilot-" + uuid.uuid4().hex,
                    permit,
                    transport,
                    limit=args.limit,
                    resume=bool(args.resume),
                )
            elif args.command == "report":
                validate_id(args.run_id)
                result = _read_json(
                    output / "runs" / args.run_id / "report.json", "report_unavailable"
                )
            else:
                transport.authorize(permit)
                with Catalog(output / "catalog", read_only=True) as catalog:
                    scope = catalog.domain(permit.domain_id)
                    documents = scope.list(Document, limit=100)
                    # A later field restriction also filters inspection of older observations.
                    observations = [
                        asdict(o)
                        for o in scope.list(Observation, limit=1000)
                        if o.field in permit.fields
                    ]
                    result = {
                        "documents_listed": len(documents),
                        "observations": observations,
                        "list_limit": 100,
                        "observation_limit": 1000,
                    }
        print(json.dumps(result, ensure_ascii=True, indent=2))
        if args.command == "validate-approval":
            return {"ready": 0, "not_authorized": 1, "invalid_configuration": 2}[result["status"]]
        return int(result.get("status") == "incomplete")
    except (DiscoveryError, CatalogError, _CLIError, OSError, ValueError, TypeError):
        error = sys.exc_info()[1]
        code = error.code if isinstance(error, DiscoveryError) else "invalid_configuration"
        print(json.dumps({"error": code}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
