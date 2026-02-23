"""Configure Python logging from DLPConfig."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "WARNING", log_file: str | None = None) -> None:
    """Configure root logger for the dlp package.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional file path. If None, logs to stderr only.
    """
    numeric_level = getattr(logging, level.upper(), logging.WARNING)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        handlers.append(file_handler)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
