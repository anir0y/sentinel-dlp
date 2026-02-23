"""Structured audit logging for DLP actions."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_log_dir

logger = logging.getLogger(__name__)

_LOG_DIR = Path(user_log_dir("dlp-tui", ensure_exists=True))
_LOG_FILE = _LOG_DIR / "audit.jsonl"


def get_audit_log_path() -> Path:
    """Return the path to the audit log file."""
    return _LOG_FILE


def log_action(
    feature: str,
    action: str,
    params: dict | None = None,
    dry_run: bool = False,
    success: bool = True,
    error: str = "",
) -> None:
    """Write a structured audit entry to the log file.

    Args:
        feature: Feature area (usb_block, usb_whitelist, hid, program_block).
        action: Action performed (block, unblock, enumerate, etc.).
        params: Optional parameters dict.
        dry_run: Whether this was a dry-run action.
        success: Whether the action succeeded.
        error: Error message if failed.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feature": feature,
        "action": action,
        "params": params or {},
        "dry_run": dry_run,
        "success": success,
        "error": error,
        "pid": os.getpid(),
    }

    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        logger.exception("Failed to write audit log")


def read_recent_entries(count: int = 50) -> list[dict]:
    """Read the most recent audit log entries."""
    if not _LOG_FILE.exists():
        return []
    entries: list[dict] = []
    try:
        with open(_LOG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to read audit log")
    return entries[-count:]
