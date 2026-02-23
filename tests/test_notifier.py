from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest


class TestSendNotification:
    """Tests for dlp.features.notifier.send_notification."""

    @patch("dlp.features.notifier.subprocess")
    @patch("dlp.features.notifier.platform")
    def test_macos_notification(self, mock_platform, mock_subprocess):
        from dlp.features.notifier import send_notification

        mock_platform.system.return_value = "Darwin"
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        send_notification(title="DLP Alert", message="Sensitive data detected")

        mock_subprocess.run.assert_called_once()
        cmd = mock_subprocess.run.call_args[0][0]

        # Should invoke osascript
        assert "osascript" in cmd or (isinstance(cmd, list) and "osascript" in cmd[0])

    @patch("dlp.features.notifier.subprocess")
    @patch("dlp.features.notifier.platform")
    def test_windows_notification(self, mock_platform, mock_subprocess):
        from dlp.features.notifier import send_notification

        mock_platform.system.return_value = "Windows"
        mock_subprocess.run.return_value = MagicMock(returncode=0)
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        send_notification(title="DLP Alert", message="Sensitive data detected")

        mock_subprocess.run.assert_called_once()
        cmd = mock_subprocess.run.call_args[0][0]

        # Should invoke powershell
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        assert "powershell" in cmd_str.lower()

    @patch("dlp.features.notifier.subprocess")
    @patch("dlp.features.notifier.platform")
    def test_notification_error_swallowed(self, mock_platform, mock_subprocess):
        from dlp.features.notifier import send_notification

        mock_platform.system.return_value = "Darwin"
        mock_subprocess.run.side_effect = subprocess.CalledProcessError(
            1, "osascript"
        )
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        # Should NOT raise
        send_notification(title="DLP Alert", message="Error test")

    @patch("dlp.features.notifier.subprocess")
    @patch("dlp.features.notifier.platform")
    def test_unsupported_platform(self, mock_platform, mock_subprocess):
        from dlp.features.notifier import send_notification

        mock_platform.system.return_value = "Linux"
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        # Should not crash on unsupported platform
        send_notification(title="DLP Alert", message="Linux test")
