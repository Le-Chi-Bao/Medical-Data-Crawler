class FoundationError(Exception):
    """Lỗi nghiệp vụ thuộc phạm vi nền tảng."""


class ConfigurationError(FoundationError):
    """Không đọc được cấu hình hợp lệ."""


class RecordValidationError(FoundationError):
    """Bản ghi vi phạm hợp đồng Structured Raw."""
