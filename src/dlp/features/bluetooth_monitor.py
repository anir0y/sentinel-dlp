"""Bluetooth device enumeration and classification."""

from __future__ import annotations

import logging
import platform
import plistlib
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BluetoothDeviceInfo:
    """Represents a discovered Bluetooth device."""

    name: str
    address: str
    device_type: str  # "audio", "input", "computer", "phone", "unknown"
    connected: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enumerate_bluetooth_devices() -> list[BluetoothDeviceInfo]:
    """Enumerate paired / visible Bluetooth devices on the current platform.

    Dispatches to a platform-specific implementation.  Returns an empty
    list on unsupported platforms or on error.
    """
    system = platform.system()

    try:
        if system == "Darwin":
            return _enumerate_darwin()
        if system == "Windows":
            return _enumerate_windows()
    except Exception:
        logger.debug("Bluetooth enumeration failed", exc_info=True)

    return []


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def _enumerate_darwin() -> list[BluetoothDeviceInfo]:
    """Enumerate Bluetooth devices on macOS via ``system_profiler``."""
    result = subprocess.run(
        ["system_profiler", "SPBluetoothDataType", "-xml"],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        logger.debug("system_profiler returned %d", result.returncode)
        return []

    plist = plistlib.loads(result.stdout)
    devices: list[BluetoothDeviceInfo] = []
    _walk_bt_tree(plist, devices)
    return devices


def _walk_bt_tree(node: object, devices: list[BluetoothDeviceInfo]) -> None:
    """Recursively walk the plist tree looking for Bluetooth device entries."""
    if isinstance(node, list):
        for item in node:
            _walk_bt_tree(item, devices)
        return

    if not isinstance(node, dict):
        return

    # Look for connected / not-connected device sections.
    for section_key in ("device_connected", "device_not_connected"):
        section = node.get(section_key)
        if not section:
            continue

        connected = section_key == "device_connected"

        # The section is typically a list of dicts where each dict has a
        # single key (the device name) mapping to the device info dict.
        if isinstance(section, list):
            for entry in section:
                if isinstance(entry, dict):
                    for dev_name, dev_info in entry.items():
                        if isinstance(dev_info, dict):
                            devices.append(
                                BluetoothDeviceInfo(
                                    name=str(dev_name),
                                    address=str(dev_info.get("device_address", "")),
                                    device_type=_classify_bt_device(dev_info),
                                    connected=connected,
                                )
                            )

    # Recurse into all dict values in case the structure is nested.
    for value in node.values():
        if isinstance(value, (dict, list)):
            _walk_bt_tree(value, devices)


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def _enumerate_windows() -> list[BluetoothDeviceInfo]:
    """Enumerate Bluetooth devices on Windows via WMI."""
    import wmi  # type: ignore[import-untyped]

    c = wmi.WMI()
    devices: list[BluetoothDeviceInfo] = []

    for entity in c.Win32_PnPEntity():
        device_id = entity.DeviceID or ""
        if "BTHENUM" not in device_id:
            continue

        name = entity.Name or "Unknown"
        address = device_id.split("\\")[-1] if "\\" in device_id else ""
        info: dict[str, str] = {"name": name}
        device_type = _classify_bt_device(info)

        devices.append(
            BluetoothDeviceInfo(
                name=name,
                address=address,
                device_type=device_type,
                connected=entity.Status == "OK",
            )
        )

    return devices


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

_AUDIO_KEYWORDS = ("audio", "headphone", "headset", "speaker", "airpod", "earphone", "earbud")
_INPUT_KEYWORDS = ("keyboard", "mouse", "trackpad", "gamepad", "joystick", "input")
_COMPUTER_KEYWORDS = ("macbook", "laptop", "desktop", "imac", "pc")
_PHONE_KEYWORDS = ("iphone", "phone", "android", "pixel", "galaxy", "samsung")


def _classify_bt_device(info: dict[str, object]) -> str:
    """Classify a Bluetooth device based on its minor_type or name keywords.

    Returns one of: ``"audio"``, ``"input"``, ``"computer"``, ``"phone"``,
    or ``"unknown"``.
    """
    # Build a searchable string from available fields.
    searchable = " ".join(
        str(info.get(key, ""))
        for key in ("device_minorType", "device_minortype", "minor_type", "name", "Name")
    ).lower()

    if any(kw in searchable for kw in _AUDIO_KEYWORDS):
        return "audio"
    if any(kw in searchable for kw in _INPUT_KEYWORDS):
        return "input"
    if any(kw in searchable for kw in _COMPUTER_KEYWORDS):
        return "computer"
    if any(kw in searchable for kw in _PHONE_KEYWORDS):
        return "phone"

    return "unknown"
