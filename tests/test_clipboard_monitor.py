from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestScanClipboard:
    """Tests for dlp.features.clipboard_monitor.scan_clipboard."""

    def test_scan_empty_text(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        alerts = scan_clipboard("")
        assert alerts == []

    def test_detect_credit_card_visa(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        alerts = scan_clipboard("Card: 4111111111111111")
        assert len(alerts) >= 1

        pattern_names = [
            getattr(a, "pattern_name", None) or getattr(a, "pattern", None)
            for a in alerts
        ]
        assert any("credit_card" in (name or "").lower() for name in pattern_names)

    def test_detect_credit_card_mastercard(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        alerts = scan_clipboard("5500000000000004")
        assert len(alerts) >= 1

        pattern_names = [
            getattr(a, "pattern_name", None) or getattr(a, "pattern", None)
            for a in alerts
        ]
        assert any("credit_card" in (name or "").lower() for name in pattern_names)

    def test_detect_ssn(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        alerts = scan_clipboard("SSN: 123-45-6789")
        assert len(alerts) >= 1

        pattern_names = [
            getattr(a, "pattern_name", None) or getattr(a, "pattern", None)
            for a in alerts
        ]
        assert any("ssn" in (name or "").lower() for name in pattern_names)

    def test_detect_aws_key(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        alerts = scan_clipboard("AKIAIOSFODNN7EXAMPLE")
        assert len(alerts) >= 1

        pattern_names = [
            getattr(a, "pattern_name", None) or getattr(a, "pattern", None)
            for a in alerts
        ]
        assert any("aws" in (name or "").lower() for name in pattern_names)

    def test_detect_private_key(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        alerts = scan_clipboard("-----BEGIN RSA PRIVATE KEY-----")
        assert len(alerts) >= 1

        pattern_names = [
            getattr(a, "pattern_name", None) or getattr(a, "pattern", None)
            for a in alerts
        ]
        assert any("private_key" in (name or "").lower() or "key" in (name or "").lower() for name in pattern_names)

    def test_no_false_positive_normal_text(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        alerts = scan_clipboard("Hello world, regular text")
        assert alerts == []

    def test_preview_truncated(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        # Use a long string containing a detectable pattern
        long_card = "Card: 4111111111111111 and a lot more text after it"
        alerts = scan_clipboard(long_card)
        assert len(alerts) >= 1

        alert = alerts[0]
        preview = getattr(alert, "preview", None) or getattr(alert, "matched_text", None)
        if preview is not None and len(preview) > 23:
            # Should be truncated to ~20 chars + "..."
            assert preview.endswith("...")

    def test_custom_patterns(self):
        from dlp.features.clipboard_monitor import scan_clipboard

        custom = {"custom_id": r"CUST-\d{6}"}
        # Text contains a custom pattern but also a credit card
        text = "CUST-123456 and Card: 4111111111111111"

        alerts = scan_clipboard(text, patterns=custom)

        pattern_names = [
            getattr(a, "pattern_name", None) or getattr(a, "pattern", None)
            for a in alerts
        ]
        # Custom pattern should match
        assert any("custom_id" in (name or "") for name in pattern_names)
        # Built-in credit_card should NOT match when custom patterns provided
        assert not any("credit_card" in (name or "").lower() for name in pattern_names)


class TestGetClipboardText:
    """Tests for dlp.features.clipboard_monitor.get_clipboard_text on macOS."""

    @patch("dlp.features.clipboard_monitor.platform")
    @patch("dlp.features.clipboard_monitor.subprocess")
    def test_get_clipboard_macos(self, mock_subprocess, mock_platform):
        from dlp.features.clipboard_monitor import get_clipboard_text

        mock_platform.system.return_value = "Darwin"

        result_mock = MagicMock()
        result_mock.stdout = "clipboard content"
        result_mock.returncode = 0
        mock_subprocess.run.return_value = result_mock

        text = get_clipboard_text()

        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args
        # pbpaste should be in the command
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        assert "pbpaste" in cmd or (isinstance(cmd, str) and "pbpaste" in cmd)
        assert text == "clipboard content"

    @patch("dlp.features.clipboard_monitor.platform")
    @patch("dlp.features.clipboard_monitor.subprocess")
    def test_get_clipboard_error_returns_empty(self, mock_subprocess, mock_platform):
        from dlp.features.clipboard_monitor import get_clipboard_text

        mock_platform.system.return_value = "Darwin"
        mock_subprocess.run.side_effect = subprocess.CalledProcessError(1, "pbpaste")
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        text = get_clipboard_text()
        assert text == "" or text is None
