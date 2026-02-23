"""USB whitelist matching logic (pure functions)."""

from __future__ import annotations

from dlp.config import WhitelistEntry


def is_device_whitelisted(
    vendor_id: str,
    product_id: str,
    serial_number: str | None,
    whitelist: list[WhitelistEntry],
) -> bool:
    """Check if a device matches any whitelist entry.

    Matching rules:
    - vendor_id and product_id must match (case-insensitive hex).
    - If the whitelist entry specifies a serial_number, it must also match.
    - If the whitelist entry has no serial_number, any serial matches.
    """
    vid = _normalize_id(vendor_id)
    pid = _normalize_id(product_id)

    for entry in whitelist:
        entry_vid = _normalize_id(entry.vendor_id)
        entry_pid = _normalize_id(entry.product_id)

        if vid != entry_vid or pid != entry_pid:
            continue

        # VID/PID matched. Check serial if the entry requires it.
        if entry.serial_number is not None:
            if serial_number is None:
                continue
            if serial_number.strip().lower() != entry.serial_number.strip().lower():
                continue

        return True

    return False


def _normalize_id(hex_id: str) -> str:
    """Normalize a hex ID for comparison (lowercase, strip '0x' prefix)."""
    return hex_id.lower().removeprefix("0x").zfill(4)
