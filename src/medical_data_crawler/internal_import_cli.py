"""Execute an explicit internal intake batch with an operator-supplied trust file."""

import argparse
import json
import sys
from pathlib import Path

from ._intake_files import MAX_INPUT_BYTES, IntakeFileError, open_local_binary
from .internal_import import IntakeError, InternalIntakeGateway, parse_authorizations

_MAX_CONFIG_BYTES = 1024 * 1024


class _CLIError(Exception):
    pass


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # The default diagnostic may echo a confidential path or argument value.
        raise _CLIError("invalid_arguments")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("invalid JSON constant")


def _read_json(path: Path, error_code: str) -> object:
    try:
        with open_local_binary(path.absolute()) as stream:
            data = stream.read(_MAX_CONFIG_BYTES + 1)
        if len(data) > _MAX_CONFIG_BYTES:
            raise ValueError("JSON configuration too large")
        return json.loads(
            data.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (IntakeFileError, OSError, ValueError, RecursionError):
        raise _CLIError(error_code) from None


def main(argv: list[str] | None = None) -> int:
    parser = _ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--spec", type=Path, required=True, help="Explicit intake specification")
    parser.add_argument(
        "--trusted-approvals", type=Path, required=True, help="Operator-controlled approvals JSON"
    )
    parser.add_argument(
        "--intake-root", type=Path, action="append", required=True, help="Approved local input root"
    )
    parser.add_argument(
        "--state-root", type=Path, required=True, help="Protected local output root"
    )
    parser.add_argument("--max-bytes", type=int, default=MAX_INPUT_BYTES, help="Input size limit")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate without storing or extracting documents"
    )
    try:
        args = parser.parse_args(argv)
        grants = parse_authorizations(
            _read_json(args.trusted_approvals, "trusted_approvals_read_error")
        )
        gateway = InternalIntakeGateway(
            approved_roots=tuple(root.absolute() for root in args.intake_root),
            state_root=args.state_root.absolute(),
            authorizations=grants,
            max_bytes=args.max_bytes,
        )
        result = gateway.run(_read_json(args.spec, "intake_spec_read_error"), dry_run=args.dry_run)
    except (IntakeError, _CLIError, OSError) as error:
        code = error.code if isinstance(error, IntakeError) else "invalid_configuration"
        if isinstance(error, _CLIError):
            code = str(error)
        print(json.dumps({"error": code}), file=sys.stderr)
        return 2

    print(json.dumps(result.report, ensure_ascii=True, indent=2))
    return int(bool(result.report["summary"]["failed"] or result.report["batch_error"]))


if __name__ == "__main__":
    raise SystemExit(main())
