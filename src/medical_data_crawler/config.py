import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError

_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    log_level: str


def load_settings(path: Path | None = None, *, env: Mapping[str, str] | None = None) -> Settings:
    """Ưu tiên biến môi trường rồi đến TOML và giá trị mặc định."""
    values = {}
    if path is not None:
        try:
            with path.open("rb") as source:
                values = tomllib.load(source)
        except (OSError, ValueError) as exc:
            raise ConfigurationError("Không đọc được file cấu hình TOML") from exc
        if values.keys() - {"data_dir", "log_level"}:
            raise ConfigurationError("Khóa cấu hình TOML không được hỗ trợ")

    environment = os.environ if env is None else env
    directory = environment.get("MDC_DATA_DIR", values.get("data_dir", "data"))
    level = environment.get("MDC_LOG_LEVEL", values.get("log_level", "INFO"))
    if not isinstance(directory, str) or not directory.strip() or "\x00" in directory:
        raise ConfigurationError("data_dir phải là đường dẫn khác rỗng")
    if not isinstance(level, str) or level.upper() not in _LEVELS:
        raise ConfigurationError("log_level không hợp lệ")
    return Settings(Path(directory), level.upper())
