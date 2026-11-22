import hashlib
import logging
from io import BytesIO
from pathlib import Path

import pytest

from medical_data_crawler.config import Settings, load_settings
from medical_data_crawler.errors import ConfigurationError
from medical_data_crawler.integrity import sha256_stream
from medical_data_crawler.logging_setup import configure_logging


def test_hash_known_vector():
    assert sha256_stream(BytesIO(b"abc")) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_binary_hash_across_reads():
    data = bytes(range(256)) * 400
    assert sha256_stream(BytesIO(data)) == hashlib.sha256(data).hexdigest()


def test_defaults_and_overrides(tmp_path):
    assert load_settings(env={}) == Settings(Path("data"), "INFO")
    path = tmp_path / "settings.toml"
    path.write_text('data_dir = "artifacts"\nlog_level = "WARNING"', encoding="utf-8")
    assert load_settings(path, env={"MDC_LOG_LEVEL": "debug"}) == Settings(
        Path("artifacts"), "DEBUG"
    )


@pytest.mark.parametrize("content", ["[", "loglevel = 3", "data_dir = 1", 'log_level = "ALL"'])
def test_bad_toml(tmp_path, content):
    path = tmp_path / "settings.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(path, env={})


def test_missing_config(tmp_path):
    with pytest.raises(ConfigurationError):
        load_settings(tmp_path / "missing", env={})


def test_invalid_environment():
    with pytest.raises(ConfigurationError):
        load_settings(env={"MDC_DATA_DIR": "  "})


def test_log_level(caplog, monkeypatch):
    logger = logging.getLogger("medical_data_crawler")
    monkeypatch.setattr(logger, "level", logger.level)
    configure_logging(load_settings(env={"MDC_LOG_LEVEL": "WARNING"}))
    logger.info("info")
    logger.warning("warning")
    assert caplog.messages == ["warning"]
