from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from autotube.core.config import Settings


def configure_logging(settings: Settings) -> logging.Logger:
    """Configura los registros de consola y archivo."""
    logger = logging.getLogger("autotube")

    if logger.handlers:
        return logger

    level = getattr(logging, settings.log_level, logging.INFO)

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    log_file = settings.logs_dir / "autotube.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger