"""Desktop notifications (best-effort, never raises)."""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def send_notification(title: str, message: str) -> None:
    """Display a desktop notification on the current platform.

    This function is best-effort: it never raises.  Failures are logged
    at debug level.

    * **macOS** — ``osascript`` with ``display notification``.
    * **Windows** — PowerShell toast notification.
    """
    system = platform.system()

    try:
        if system == "Darwin":
            _notify_macos(title, message)
        elif system == "Windows":
            _notify_windows(title, message)
        else:
            logger.debug("Desktop notifications not supported on %s", system)
    except Exception:
        logger.debug("Failed to send notification", exc_info=True)


def _notify_macos(title: str, message: str) -> None:
    """Send a notification on macOS via osascript."""
    # Escape double-quotes to prevent AppleScript injection.
    safe_title = title.replace('"', '\\"')
    safe_message = message.replace('"', '\\"')

    script = f'display notification "{safe_message}" with title "{safe_title}"'
    subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        timeout=10,
    )


def _notify_windows(title: str, message: str) -> None:
    """Send a toast notification on Windows via PowerShell."""
    # Escape single-quotes for PowerShell string literals.
    safe_title = title.replace("'", "''")
    safe_message = message.replace("'", "''")

    ps_script = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] > $null; "
        "$template = [Windows.UI.Notifications.ToastNotificationManager]::"
        "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        "$textNodes = $template.GetElementsByTagName('text'); "
        f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{safe_title}')) > $null; "
        f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{safe_message}')) > $null; "
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
        "[Windows.UI.Notifications.ToastNotificationManager]::"
        "CreateToastNotifier('DLP-TUI').Show($toast)"
    )
    subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True,
        timeout=10,
    )
