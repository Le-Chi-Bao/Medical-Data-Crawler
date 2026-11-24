"""Print sanitized preflight observations for an authorized local HTML file."""

import argparse
import json

from medical_data_crawler.html_preflight import (
    DEFAULT_MAX_BYTES,
    HTTP_EVIDENCE_FIELDS,
    MAX_INPUT_BYTES,
    inspect_html,
)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "INVALID_ARGUMENTS (see --help)\n")


def main() -> int:
    parser = _ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("html_file", help="Authorized file on a local disk")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Input limit in bytes (1 to {MAX_INPUT_BYTES}; default %(default)s)",
    )
    parser.add_argument(
        "--http-evidence-field",
        action="append",
        choices=HTTP_EVIDENCE_FIELDS,
        default=[],
        help="Mark a field as held separately. Repeat for each field. Supply field names only.",
    )
    args = parser.parse_args()
    report = inspect_html(
        args.html_file, max_bytes=args.max_bytes, supplied_http_fields=args.http_evidence_field
    )
    print(json.dumps(report, indent=2))
    return int(report["review_readiness"] == "INSPECTION_INCOMPLETE")


if __name__ == "__main__":
    raise SystemExit(main())
