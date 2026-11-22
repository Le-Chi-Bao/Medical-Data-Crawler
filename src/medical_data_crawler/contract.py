import json
from functools import cache
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

from .errors import RecordValidationError


@cache
def _validator() -> Draft202012Validator:
    resource = files("medical_data_crawler").joinpath("schemas/structured-raw-0.1.json")
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker(formats=["date-time"]))


def validate_record(record: object) -> None:
    """Kiểm tra bản ghi đã giải mã từ JSON, không sửa hoặc ghi log nội dung."""
    error = next(_validator().iter_errors(record), None)
    if error is not None:
        # Chỉ dùng đường dẫn trong schema để tránh lộ giá trị hoặc khóa từ tài liệu.
        path = "/".join(map(str, error.absolute_schema_path))
        raise RecordValidationError(f"Bản ghi vi phạm schema tại {path}")
