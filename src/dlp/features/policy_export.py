"""Policy configuration export and import."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dlp.config import DLPConfig

logger = logging.getLogger(__name__)


def export_policy(config: DLPConfig, path: Path) -> None:
    """Export a :class:`DLPConfig` to a JSON file at *path*.

    Creates parent directories if they do not exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)

    logger.info("Policy exported to %s", path)


def import_policy(path: Path) -> DLPConfig:
    """Import a :class:`DLPConfig` from a JSON file at *path*.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file contents are not valid JSON or fail
            schema validation.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Policy file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in policy file: {exc}") from exc

    try:
        config = DLPConfig.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Policy validation failed: {exc}") from exc

    logger.info("Policy imported from %s", path)
    return config
