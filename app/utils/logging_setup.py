"""Logging configuration for SmartSort."""
from __future__ import annotations
import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_dir: Path, log_level: int = logging.INFO) -> None:
    """Configure application-wide logging with rotating file output."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "smartsort.log"

    root = logging.getLogger()
    root.setLevel(log_level)

    # 5 MB per file, keep 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Console: warnings and above only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )

    root.addHandler(file_handler)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
