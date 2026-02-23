"""Clipboard monitoring for sensitive data patterns."""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_PATTERNS: dict[str, str] = {
    "credit_card": (
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}"
        r"|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
    ),
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "api_key_generic": (
        r"\b(?:api[_-]?key|apikey|secret[_-]?key)\s*[:=]\s*['\"]?[\w\-]{16,}['\"]?\b"
    ),
    "aws_key": r"\bAKIA[0-9A-Z]{16}\b",
    "private_key": r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
}


@dataclass(frozen=True)
class ClipboardAlert:
    """Alert raised when clipboard text matches a sensitive data pattern."""

    pattern_name: str
    matched_text_preview: str  # first 20 characters of the match


def get_clipboard_text() -> str:
    """Read the current system clipboard as plain text.

    macOS: uses ``pbpaste``.
    Windows: uses ``win32clipboard``.

    Returns an empty string on failure or unsupported platforms.
    """
    system = platform.system()

    try:
        if system == "Darwin":
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout

        if system == "Windows":
            import win32clipboard  # type: ignore[import-untyped]

            win32clipboard.OpenClipboard()
            try:
                data = win32clipboard.GetClipboardData()
                return str(data) if data else ""
            finally:
                win32clipboard.CloseClipboard()

    except Exception:
        logger.debug("Failed to read clipboard", exc_info=True)

    return ""


def scan_clipboard(
    text: str,
    patterns: dict[str, str] | None = None,
) -> list[ClipboardAlert]:
    """Scan *text* for sensitive data patterns.

    This is a pure function: it does not access the clipboard itself.
    If *patterns* is ``None``, :data:`DEFAULT_PATTERNS` is used.

    Returns a list of :class:`ClipboardAlert` for each pattern that matched.
    """
    if not text:
        return []

    if patterns is None:
        patterns = DEFAULT_PATTERNS

    alerts: list[ClipboardAlert] = []
    for name, regex in patterns.items():
        try:
            match = re.search(regex, text, re.IGNORECASE)
        except re.error:
            logger.warning("Invalid regex for pattern %r — skipped", name)
            continue

        if match:
            preview = match.group()[:20]
            alerts.append(ClipboardAlert(pattern_name=name, matched_text_preview=preview))

    return alerts
