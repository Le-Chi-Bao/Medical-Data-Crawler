"""Bounded, offline reconciliation of explicitly mapped legacy batches.

Only legacy references are published. Target entities and domain selection are
trusted operator inputs; this service never creates identities or grants rights.
"""

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from .._intake_files import IntakeFileError, check_local_path
from ..export import ExportError, _read_file, validate_manifest, verify_batch
from ..provenance import ProvenanceStore
from ._legacy import read_verified_entry
from .model import CatalogError, validate_id
from .store import DomainCatalog

MAX_ITEMS = 128
MAX_MANIFEST_BYTES = 256 * 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
STATUSES = ("linked", "already_linked", "needs_review", "skipped", "failed")


@dataclass(frozen=True)
class Mapping:
    input_index: int
    legacy_source_id: str
    source_item_id: str
    rendition_id: str


@dataclass(frozen=True)
class BatchInput:
    manifest_path: Path
    manifest_sha256: str
    domain_id: str
    mappings: Iterable[Mapping]


def _mappings(values: Iterable[Mapping]) -> tuple[dict[int, Mapping], set[int]]:
    bounded = tuple(islice(values, MAX_ITEMS + 1))
    if len(bounded) > MAX_ITEMS:
        raise CatalogError("mapping_size_limit")
    mappings, conflicts = {}, set()
    for value in bounded:
        if (
            type(value) is not Mapping
            or type(value.input_index) is not int
            or not 0 <= value.input_index < MAX_ITEMS
        ):
            raise CatalogError("mapping_invalid")
        for text in (value.legacy_source_id, value.source_item_id, value.rendition_id):
            validate_id(text)
        # Duplicate declarations are ambiguous even if they happen to be identical.
        if value.input_index in mappings:
            conflicts.add(value.input_index)
        mappings[value.input_index] = value
    return mappings, conflicts


class BackfillService:
    def __init__(self, scope: DomainCatalog, provenance: ProvenanceStore):
        self.scope = scope
        self.provenance = provenance
        try:
            check_local_path(provenance.root.absolute())
            check_local_path(provenance.artifacts.root.absolute())
        except IntakeFileError:
            raise CatalogError("store_path_invalid") from None

    def run(self, batches: Iterable[BatchInput], *, dry_run: bool = True) -> Iterator[dict]:
        """Yield one sanitized report per explicit batch; never retain a corpus inventory.

        Dry-run eligible items have status skipped/code would_link. Execution repeats
        verification and binding checks; a dry-run report is not a publication permit.
        """
        for batch_index, batch in enumerate(batches):
            try:
                report = self._batch(batch, dry_run)
            except (CatalogError, ExportError) as error:
                report = self._report([], dry_run, "failed", error.code)
            except Exception:
                # Files, JSON parsers and database drivers must not leak submitted text.
                report = self._report([], dry_run, "failed", "backfill_input_error")
            yield {"batch_index": batch_index, **report}

    @staticmethod
    def _report(items, dry_run, verification, batch_code=None):
        counts = Counter(item["status"] for item in items)
        reasons = Counter(item["code"] for item in items)
        return dict(
            backfill_report_version="0.1",
            dry_run=dry_run,
            verification=verification,
            batch_code=batch_code,
            counts={status: counts[status] for status in STATUSES},
            reasons=dict(sorted(reasons.items())),
            reconciliation=dict(
                mapping_failures=sum(
                    count for code, count in reasons.items() if code.startswith("mapping_")
                ),
                conflicts=reasons["mapping_conflict"] + reasons["record_conflict"],
                missing_references=reasons["reference_missing"],
                integrity_failures=reasons["batch_integrity_failed"]
                + reasons["legacy_batch_invalid"],
            ),
            items=items,
        )

    def _batch(self, batch, dry_run):
        if type(batch) is not BatchInput or batch.domain_id != self.scope.access_domain.id:
            raise CatalogError("domain_mismatch")
        if not isinstance(batch.manifest_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", batch.manifest_sha256
        ):
            raise CatalogError("manifest_pin_invalid")
        mappings, conflicts = _mappings(batch.mappings)
        try:
            return self._mapped_batch(batch, dry_run, mappings, conflicts)
        except (CatalogError, ExportError) as error:
            code = error.code
        except Exception:
            code = "backfill_input_error"
        items = [dict(input_index=i, status="failed", code=code) for i in sorted(mappings)]
        return self._report(items, dry_run, "failed", code)

    def _mapped_batch(self, batch, dry_run, mappings, conflicts):
        try:
            path = check_local_path(Path(batch.manifest_path).absolute())
        except IntakeFileError:
            raise CatalogError("manifest_path_invalid") from None
        payload = _read_file(path, "manifest_read_error", MAX_MANIFEST_BYTES)
        if hashlib.sha256(payload).hexdigest() != batch.manifest_sha256:
            raise CatalogError("manifest_pin_mismatch")
        manifest = json.loads(payload)
        if isinstance(manifest, dict) and any(
            isinstance(manifest.get(key), list) and len(manifest[key]) > MAX_ITEMS
            for key in ("records", "omissions")
        ):
            raise CatalogError("batch_size_limit")
        validate_manifest(manifest)
        if manifest["summary"]["total"] > MAX_ITEMS:
            raise CatalogError("batch_size_limit")
        verified = verify_batch(path, self.provenance, max_file_bytes=MAX_FILE_BYTES)
        if not verified.valid:
            # Pin a single failure to every known input, without revealing which domain it held.
            items = [
                dict(input_index=i, status="failed", code="batch_integrity_failed")
                for i in range(manifest["summary"]["total"])
            ]
            return self._report(items, dry_run, "failed", "batch_integrity_failed")
        # Detect a manifest replaced between quota/pin validation and verification.
        if verified.manifest != manifest:
            raise CatalogError("manifest_pin_mismatch")

        planned, items = {}, {}
        owners = {}
        for entry in sorted(manifest["records"], key=lambda e: e["input_index"]):
            index = entry["input_index"]
            item = dict(input_index=index, status="needs_review", code="mapping_missing")
            items[index] = item
            if index in conflicts:
                item["code"] = "mapping_conflict"
                continue
            mapping = mappings.get(index)
            if mapping is None:
                continue
            try:
                reference, media, size = read_verified_entry(
                    path,
                    self.provenance,
                    index,
                    self.scope.access_domain,
                    manifest,
                    max_file_bytes=MAX_FILE_BYTES,
                )
                if reference["source_id"] != mapping.legacy_source_id:
                    raise CatalogError("source_binding_mismatch")
                legacy, _ = self.scope._link_legacy(
                    reference,
                    media,
                    size,
                    mapping.source_item_id,
                    mapping.rendition_id,
                    dry_run=True,
                )
                owners.setdefault(legacy.legacy_document_id, {}).setdefault(
                    legacy.document_id, []
                ).append(index)
                planned[index] = (reference, media, size, mapping)
                item["code"] = "ready"
            except CatalogError as error:
                item["code"] = self._reason(error)
        # Reject all competing owners in this batch before the first publication.
        for documents in owners.values():
            if len(documents) > 1:
                for indices in documents.values():
                    for index in indices:
                        items[index]["code"] = "mapping_conflict"
        for index, (reference, media, size, mapping) in planned.items():
            item = items[index]
            if item["code"] != "ready":
                continue
            try:
                if not dry_run:
                    payload = _read_file(path, "manifest_read_error", MAX_MANIFEST_BYTES)
                    if hashlib.sha256(payload).hexdigest() != batch.manifest_sha256:
                        raise CatalogError("legacy_batch_invalid")
                    # Re-read the bounded record/event and stream-check the original
                    # immediately before publication; never execute a stale plan.
                    reference, media, size = read_verified_entry(
                        path,
                        self.provenance,
                        index,
                        self.scope.access_domain,
                        manifest,
                        max_file_bytes=MAX_FILE_BYTES,
                    )
                _, existing = self.scope._link_legacy(
                    reference,
                    media,
                    size,
                    mapping.source_item_id,
                    mapping.rendition_id,
                    dry_run=dry_run,
                )
                item.update(
                    status="already_linked" if existing else "skipped" if dry_run else "linked",
                    code="already_linked" if existing else "would_link" if dry_run else "linked",
                )
            except CatalogError as error:
                item.update(status="failed", code=self._reason(error))
            except ExportError:
                item.update(status="failed", code="legacy_batch_invalid")
            except Exception:
                item.update(status="failed", code="publication_failed")
        for omission in manifest["omissions"]:
            index = omission["input_index"]
            items[index] = dict(input_index=index, status="skipped", code="legacy_omission")
        for index in mappings.keys() - items.keys():
            items[index] = dict(input_index=index, status="needs_review", code="reference_missing")
        report = self._report([items[i] for i in sorted(items)], dry_run, "pass")
        report["extraction"] = manifest["summary"]["extraction"]
        report["legacy_gaps"] = ["logical_key_not_reconstructed", "block_locators_not_backfilled"]
        return report

    @staticmethod
    def _reason(error):
        # Whitelist codes from the primitive; never echo a dynamic exception string.
        return (
            error.code
            if error.code
            in {
                "legacy_binding_mismatch",
                "source_binding_mismatch",
                "record_conflict",
                "database_busy",
                "database_error",
                "legacy_batch_invalid",
            }
            else "reference_invalid"
        )
