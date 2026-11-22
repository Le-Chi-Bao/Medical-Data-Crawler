import logging

from .config import Settings


def configure_logging(settings: Settings) -> None:
    """Entry point gọi một lần khi khởi động. Tôn trọng handler của ứng dụng chủ."""
    logging.basicConfig(format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("medical_data_crawler").setLevel(settings.log_level)
