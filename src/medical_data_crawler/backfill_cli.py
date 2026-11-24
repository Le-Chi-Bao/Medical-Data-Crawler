"""Offline JSONL interface: python -m medical_data_crawler.backfill_cli --help."""

import argparse
import json
from pathlib import Path

from ._intake_files import IntakeFileError, check_local_path
from .catalog import Catalog, CatalogError
from .catalog.backfill import MAX_MANIFEST_BYTES, BackfillService, BatchInput, Mapping
from .provenance import ProvenanceStore
from .storage import ArtifactStore


def read_inputs(path: Path):
    """One bounded mapping envelope per line; paths are relative to the input file."""
    with path.open("rb") as stream:
        while line := stream.readline(MAX_MANIFEST_BYTES + 1):
            if len(line) > MAX_MANIFEST_BYTES:
                raise CatalogError("mapping_size_limit")
            try:
                value = json.loads(line)
                if (
                    value.keys()
                    != {
                        "backfill_version",
                        "domain_id",
                        "manifest_path",
                        "manifest_sha256",
                        "mappings",
                    }
                    or value["backfill_version"] != "0.1"
                ):
                    raise ValueError
                yield BatchInput(
                    path.parent / value["manifest_path"],
                    value["manifest_sha256"],
                    value["domain_id"],
                    tuple(Mapping(**row) for row in value["mappings"]),
                )
            except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
                raise CatalogError("mapping_invalid") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("catalog", "domain", "events", "originals", "inputs"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--execute", action="store_true", help="Publish links; default is dry-run")
    args = parser.parse_args(argv)
    try:
        # Validate local, existing roots before store constructors can create directories.
        roots = {
            key: check_local_path(Path(getattr(args, key)).absolute())
            for key in ("catalog", "events", "originals", "inputs")
        }
        if not all(roots[key].is_dir() for key in ("catalog", "events", "originals")):
            raise CatalogError("store_path_invalid")
        provenance = ProvenanceStore(roots["events"], ArtifactStore(roots["originals"]))
        failed = False
        with Catalog(roots["catalog"], read_only=not args.execute) as catalog:
            service = BackfillService(catalog.domain(args.domain), provenance)
            for report in service.run(read_inputs(roots["inputs"]), dry_run=not args.execute):
                print(json.dumps(report, sort_keys=True))
                failed |= bool(
                    report["batch_code"]
                    or report["counts"]["failed"]
                    or report["counts"]["needs_review"]
                )
            catalog.verify()
        return 1 if failed else 0
    except (CatalogError, IntakeFileError) as error:
        print(json.dumps({"error": error.code}))
    except Exception:
        print(json.dumps({"error": "backfill_input_error"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
