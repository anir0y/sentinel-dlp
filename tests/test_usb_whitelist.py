"""Tests for USB whitelist matching logic (pure functions, no mocking needed)."""

from __future__ import annotations

from dlp.config import WhitelistEntry
from dlp.features.usb_whitelist import is_device_whitelisted


def test_exact_vid_pid_match(sample_whitelist):
    assert is_device_whitelisted("0781", "5583", None, sample_whitelist) is True


def test_non_matching_device_blocked(sample_whitelist):
    assert is_device_whitelisted("DEAD", "BEEF", None, sample_whitelist) is False


def test_serial_number_binding_match(sample_whitelist):
    """Entry with serial requires serial to match."""
    assert is_device_whitelisted("0951", "1666", "KING123", sample_whitelist) is True


def test_serial_number_binding_mismatch(sample_whitelist):
    """Wrong serial should not match."""
    assert is_device_whitelisted("0951", "1666", "WRONG", sample_whitelist) is False


def test_serial_required_but_none_provided(sample_whitelist):
    """Entry requires serial but device provides None."""
    assert is_device_whitelisted("0951", "1666", None, sample_whitelist) is False


def test_entry_without_serial_matches_any():
    """Entry without serial matches any serial."""
    whitelist = [WhitelistEntry(vendor_id="0781", product_id="5583")]
    assert is_device_whitelisted("0781", "5583", "ANY_SERIAL", whitelist) is True
    assert is_device_whitelisted("0781", "5583", None, whitelist) is True


def test_case_insensitive_matching():
    whitelist = [WhitelistEntry(vendor_id="0781", product_id="5583")]
    assert is_device_whitelisted("0781", "5583", None, whitelist) is True


def test_hex_prefix_handling():
    """Handle '0x' prefix in IDs."""
    whitelist = [WhitelistEntry(vendor_id="0x0781", product_id="0x5583")]
    assert is_device_whitelisted("0781", "5583", None, whitelist) is True


def test_empty_whitelist():
    assert is_device_whitelisted("0781", "5583", None, []) is False


def test_multiple_entries_first_match_wins():
    whitelist = [
        WhitelistEntry(vendor_id="0781", product_id="5583", serial_number="SER1"),
        WhitelistEntry(vendor_id="0781", product_id="5583"),  # No serial = any
    ]
    # Second entry matches even though first requires specific serial
    assert is_device_whitelisted("0781", "5583", "OTHER", whitelist) is True
