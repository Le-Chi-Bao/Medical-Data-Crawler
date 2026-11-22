import json
from pathlib import Path

import pytest

from medical_data_crawler.contract import validate_record
from medical_data_crawler.errors import RecordValidationError


@pytest.fixture
def record():
    return json.loads((Path(__file__).parents[1] / "fixtures/record.json").read_text("utf-8"))


def test_record_with_unknown_fields(record):
    validate_record(record)


def test_supported_labels(record):
    record.update(scope=[f"K{i:02}" for i in range(1, 9)], scope_evidence="Bộ mẫu đã gán nhãn")
    validate_record(record)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("schema_version", "1.0"),
        ("original.sha256", "A" * 64),
        ("original.sha256", "a" * 63),
        ("source.acquired_at", "2026-11-31T29:00:00Z"),
        ("scope", ["K09"]),
        ("scope", ["K01"]),
        ("audience", "medical"),
        ("rights.reuse", "permitted"),
        ("content", []),
        ("extraction.errors", ["Lỗi đọc"]),
    ],
)
def test_invalid_record(record, path, value):
    parent = record
    *prefix, field = path.split(".")
    for name in prefix:
        parent = parent[name]
    parent[field] = value
    with pytest.raises(RecordValidationError):
        validate_record(record)


def test_required_metadata_container(record):
    del record["metadata"]
    with pytest.raises(RecordValidationError):
        validate_record(record)


def test_partial_requires_warning(record):
    record["extraction"]["status"] = "partial"
    with pytest.raises(RecordValidationError):
        validate_record(record)
    record["extraction"]["warnings"] = ["Thiếu bảng"]
    validate_record(record)


def test_failed_record_retains_provenance(record):
    record["extraction"].update(status="failed", errors=["Lỗi đọc"])
    with pytest.raises(RecordValidationError):
        validate_record(record)
    record["content"] = []
    validate_record(record)
    record["extraction"]["errors"] = []
    with pytest.raises(RecordValidationError):
        validate_record(record)
