"""Platform detection and factory functions."""

from __future__ import annotations

import platform as _platform

from dlp.platform.base import ProgramBlockerBase, USBManagerBase


def get_usb_manager(dry_run: bool = False) -> USBManagerBase:
    """Return the platform-appropriate USB manager."""
    system = _platform.system()
    if system == "Windows":
        from dlp.platform.windows import WindowsUSBManager

        return WindowsUSBManager(dry_run=dry_run)
    elif system == "Darwin":
        from dlp.platform.darwin import DarwinUSBManager

        return DarwinUSBManager(dry_run=dry_run)
    elif system == "Linux":
        from dlp.platform.linux import LinuxUSBManager

        return LinuxUSBManager(dry_run=dry_run)
    raise RuntimeError(f"Unsupported platform: {system}")


def get_program_blocker(dry_run: bool = False) -> ProgramBlockerBase | None:
    """Return the program blocker (Windows only). Returns None on other OS."""
    system = _platform.system()
    if system == "Windows":
        from dlp.platform.windows import WindowsProgramBlocker

        return WindowsProgramBlocker(dry_run=dry_run)
    return None


def is_admin() -> bool:
    """Check if the current process has admin/root privileges."""
    system = _platform.system()
    if system == "Windows":
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    else:
        import os

        return os.geteuid() == 0


def get_platform_name() -> str:
    """Return a human-readable platform name."""
    system = _platform.system()
    if system == "Darwin":
        return f"macOS {_platform.mac_ver()[0]}"
    elif system == "Windows":
        return f"Windows {_platform.version()}"
    elif system == "Linux":
        try:
            import distro  # type: ignore[import-untyped]

            return f"Linux {distro.name()} {distro.version()}"
        except ImportError:
            return f"Linux {_platform.release()}"
    return system
