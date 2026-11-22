from importlib.resources import files
from json import loads

import pytest
from jsonschema import Draft202012Validator

from medical_data_crawler.export import ExportError, validate_manifest


@pytest.mark.parametrize("name", ["structured-raw-0.1.json", "export-manifest-0.1.json"])
def test_packaged_schema_is_valid(name):
    schema = files("medical_data_crawler").joinpath("schemas", name)
    Draft202012Validator.check_schema(loads(schema.read_text(encoding="utf-8")))


def test_manifest_with_only_failed_and_skipped_items():
    skipped = {
        "input_index": 0,
        "document_id": None,
        "event_id": None,
        "status": "skipped",
        "code": "missing_access_basis",
    }
    failed = {**skipped, "input_index": 1, "status": "failed", "code": "acquisition_failed"}
    manifest = {
        "manifest_version": "0.1",
        "batch_id": "a" * 32,
        "created_at": "2026-11-23T10:15:00+07:00",
        "structured_raw_version": "0.1",
        "records": [],
        "omissions": [skipped, failed],
        "summary": {
            "total": 2,
            "exported": 0,
            "failed": 1,
            "skipped": 1,
            "extraction": {"success": 0, "partial": 0, "failed": 0},
        },
    }
    validate_manifest(manifest)
    with pytest.raises(ExportError, match="^manifest_invalid$"):
        validate_manifest({**manifest, "omissions": [skipped, {**failed, "input_index": 0}]})
    with pytest.raises(ExportError, match="^manifest_invalid$"):
        validate_manifest({**manifest, "omissions": [skipped, {**failed, "code": "raw message"}]})
