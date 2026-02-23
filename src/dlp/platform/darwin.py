"""macOS platform implementation using ioreg, system_profiler, and diskutil."""

from __future__ import annotations

import logging
import plistlib
import re
import subprocess
import threading

from dlp.constants import DARWIN_POLL_INTERVAL
from dlp.platform.base import BlockRule, ProgramBlockerBase, USBDeviceInfo, USBManagerBase

logger = logging.getLogger(__name__)


class DarwinUSBManager(USBManagerBase):
    """macOS USB management via ioreg (primary), system_profiler (fallback), diskutil."""

    def __init__(self, dry_run: bool = False) -> None:
        super().__init__(dry_run=dry_run)
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop = threading.Event()
        self._blocked_devices: set[tuple[str, str]] = set()
        self._storage_blocked = False

    def enumerate_devices(self) -> list[USBDeviceInfo]:
        """Enumerate USB devices. Uses ioreg (primary), falls back to system_profiler."""
        devices = _enumerate_via_ioreg()
        if devices:
            return devices

        # Fallback: system_profiler (works on older macOS / Intel Macs)
        logger.debug("ioreg returned no devices, falling back to system_profiler")
        return _enumerate_via_system_profiler()

    def enumerate_hid_devices(self) -> list[USBDeviceInfo]:
        all_devices = self.enumerate_devices()
        return [d for d in all_devices if d.device_class == "hid"]

    def block_mass_storage(self) -> None:
        if self.dry_run:
            logger.info("[DRY RUN] Would start USB storage monitor daemon")
            self._storage_blocked = True
            return
        self._storage_blocked = True
        self._start_storage_monitor()
        logger.info("USB storage monitor started (will eject external drives)")

    def unblock_mass_storage(self) -> None:
        if self.dry_run:
            logger.info("[DRY RUN] Would stop USB storage monitor daemon")
            self._storage_blocked = False
            return
        self._storage_blocked = False
        self._stop_storage_monitor()
        logger.info("USB storage monitor stopped")

    def is_mass_storage_blocked(self) -> bool:
        return self._storage_blocked

    def block_device(self, vendor_id: str, product_id: str) -> None:
        vid = _normalize_vid(vendor_id)
        pid = _normalize_vid(product_id)
        if self.dry_run:
            logger.info("[DRY RUN] Would block device VID:%s PID:%s", vid, pid)
            self._blocked_devices.add((vid, pid))
            return
        self._blocked_devices.add((vid, pid))
        logger.info("Added device VID:%s PID:%s to block list", vid, pid)

    def allow_device(self, vendor_id: str, product_id: str) -> None:
        vid = _normalize_vid(vendor_id)
        pid = _normalize_vid(product_id)
        self._blocked_devices.discard((vid, pid))
        if self.dry_run:
            logger.info("[DRY RUN] Would allow device VID:%s PID:%s", vid, pid)
            return
        logger.info("Removed device VID:%s PID:%s from block list", vid, pid)

    def get_blocked_devices(self) -> list[tuple[str, str]]:
        return list(self._blocked_devices)

    def _start_storage_monitor(self) -> None:
        """Start a background thread that ejects non-whitelisted external disks."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_stop.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="usb-monitor"
        )
        self._monitor_thread.start()

    def _stop_storage_monitor(self) -> None:
        """Stop the storage monitor thread."""
        self._monitor_stop.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=DARWIN_POLL_INTERVAL + 1)
            self._monitor_thread = None

    def _monitor_loop(self) -> None:
        """Poll for external disks and eject them."""
        import time

        consecutive_errors = 0
        max_consecutive = 5

        while not self._monitor_stop.is_set():
            try:
                disks = _get_external_disks()
                for disk_id in disks:
                    logger.info("Ejecting external disk: %s", disk_id)
                    _eject_disk(disk_id)
                consecutive_errors = 0
            except subprocess.CalledProcessError as e:
                consecutive_errors += 1
                logger.error("Storage monitor: command failed: %s", e)
                if consecutive_errors >= max_consecutive:
                    logger.error(
                        "Storage monitor: %d consecutive errors, stopping",
                        consecutive_errors,
                    )
                    self._storage_blocked = False
                    break
            except Exception:
                consecutive_errors += 1
                logger.exception("Unexpected error in storage monitor")
                if consecutive_errors >= max_consecutive:
                    logger.error(
                        "Storage monitor: %d consecutive errors, stopping",
                        consecutive_errors,
                    )
                    self._storage_blocked = False
                    break
            time.sleep(DARWIN_POLL_INTERVAL)


class DarwinProgramBlocker(ProgramBlockerBase):
    """Stub program blocker for macOS (feature not available)."""

    def block_path(self, path_pattern: str, description: str = "") -> str:
        raise NotImplementedError("Program blocking is not available on macOS")

    def unblock_path(self, rule_id: str) -> None:
        raise NotImplementedError("Program blocking is not available on macOS")

    def list_rules(self) -> list[BlockRule]:
        return []

    def is_available(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# ioreg-based enumeration (primary — works on Apple Silicon + modern macOS)
# ---------------------------------------------------------------------------

# Regex patterns for parsing ioreg output
_RE_NODE_START = re.compile(r"\+-o\s+(.+?)\s+<class\s+(\S+),")
_RE_KV_INT = re.compile(r'"([^"]+?)"\s*=\s*(\d+)\s*$')
_RE_KV_STR = re.compile(r'"([^"]+?)"\s*=\s*"(.*?)"\s*$')

# USB device class codes (bDeviceClass)
_USB_CLASS_MASS_STORAGE = 8
_USB_CLASS_HID = 3
_USB_CLASS_HUB = 9
_USB_CLASS_AUDIO = 1
_USB_CLASS_COMPOSITE = 0  # composite devices declare class per-interface


def _enumerate_via_ioreg() -> list[USBDeviceInfo]:
    """Parse `ioreg -p IOUSB -l -w0` to enumerate USB devices."""
    try:
        result = subprocess.run(
            ["ioreg", "-p", "IOUSB", "-l", "-w0"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    devices: list[USBDeviceInfo] = []
    current: dict[str, str | int] = {}
    node_name = ""

    for line in result.stdout.splitlines():
        # New node boundary
        node_match = _RE_NODE_START.search(line)
        if node_match:
            # Flush previous node if it had a vendor ID
            if "idVendor" in current:
                devices.append(_ioreg_node_to_device(current, node_name))
            current = {}
            node_name = node_match.group(1)
            continue

        # Integer key-value (idVendor, idProduct, bDeviceClass, etc.)
        int_match = _RE_KV_INT.search(line)
        if int_match:
            current[int_match.group(1)] = int(int_match.group(2))
            continue

        # String key-value (USB Product Name, USB Vendor Name, etc.)
        str_match = _RE_KV_STR.search(line)
        if str_match:
            current[str_match.group(1)] = str_match.group(2)
            continue

    # Flush last node
    if "idVendor" in current:
        devices.append(_ioreg_node_to_device(current, node_name))

    return devices


def _ioreg_node_to_device(props: dict, node_name: str) -> USBDeviceInfo:
    """Convert a parsed ioreg property dict into a USBDeviceInfo."""
    vid_int = int(props.get("idVendor", 0))
    pid_int = int(props.get("idProduct", 0))
    vid = f"{vid_int:04x}"
    pid = f"{pid_int:04x}"

    product_name = str(props.get("USB Product Name", node_name or "Unknown"))
    manufacturer = str(props.get("USB Vendor Name", "Unknown"))
    serial = str(props.get("USB Serial Number", ""))

    device_class_code = int(props.get("bDeviceClass", -1))
    device_class = _classify_usb_class(device_class_code, product_name)

    return USBDeviceInfo(
        vendor_id=vid,
        product_id=pid,
        serial_number=serial,
        manufacturer=manufacturer,
        product_name=product_name,
        device_class=device_class,
        device_path=node_name,
    )


def _classify_usb_class(bdev_class: int, product_name: str) -> str:
    """Classify device using bDeviceClass code + product name heuristics."""
    # Direct class code match
    if bdev_class == _USB_CLASS_MASS_STORAGE:
        return "mass_storage"
    if bdev_class == _USB_CLASS_HID:
        return "hid"
    if bdev_class == _USB_CLASS_HUB:
        return "hub"
    if bdev_class == _USB_CLASS_AUDIO:
        return "audio"

    # For composite devices (class 0) or unknown, use product name heuristics
    name_lower = product_name.lower()

    storage_kw = ("storage", "disk", "flash", "drive", "thumb", "usb mass")
    if any(kw in name_lower for kw in storage_kw):
        return "mass_storage"

    hid_kw = ("keyboard", "mouse", "trackpad", "touch", "gamepad", "joystick")
    if any(kw in name_lower for kw in hid_kw):
        return "hid"

    if "hub" in name_lower:
        return "hub"

    audio_kw = ("audio", "speaker", "microphone", "headset", "headphone")
    if any(kw in name_lower for kw in audio_kw):
        return "audio"

    # Phone/Android/iPhone devices are often composite (MTP/PTP + ADB)
    phone_kw = ("android", "iphone", "pixel", "galaxy", "samsung", "oneplus", "xiaomi", "mtp")
    if any(kw in name_lower for kw in phone_kw):
        return "mass_storage"

    return "other"


# ---------------------------------------------------------------------------
# system_profiler-based enumeration (fallback for older macOS / Intel Macs)
# ---------------------------------------------------------------------------


def _enumerate_via_system_profiler() -> list[USBDeviceInfo]:
    """Parse `system_profiler SPUSBDataType -xml` for USB devices."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-xml"],
            capture_output=True,
            check=True,
        )
        plist_data = plistlib.loads(result.stdout)
        devices: list[USBDeviceInfo] = []
        _walk_usb_tree(plist_data, devices)
        return devices
    except (subprocess.CalledProcessError, plistlib.InvalidFileException):
        return []


def _walk_usb_tree(node: object, devices: list[USBDeviceInfo]) -> None:
    """Recursively walk the SPUSBDataType plist structure."""
    if isinstance(node, list):
        for item in node:
            _walk_usb_tree(item, devices)
    elif isinstance(node, dict):
        if "vendor_id" in node:
            devices.append(
                USBDeviceInfo(
                    vendor_id=_extract_hex(node.get("vendor_id", "")),
                    product_id=_extract_hex(node.get("product_id", "")),
                    serial_number=node.get("serial_num", ""),
                    manufacturer=node.get("manufacturer", "Unknown"),
                    product_name=node.get("_name", "Unknown"),
                    device_class=_classify_from_plist(node),
                    device_path=str(node.get("location_id", "")),
                )
            )
        if "_items" in node:
            _walk_usb_tree(node["_items"], devices)


def _extract_hex(value: str) -> str:
    """Extract hex value from strings like '0x0781 (SanDisk)'."""
    if not value:
        return "0000"
    value = value.strip()
    if " " in value:
        value = value.split()[0]
    return value.lower().removeprefix("0x").zfill(4)


def _classify_from_plist(node: dict) -> str:
    """Classify a device based on its plist properties."""
    name = node.get("_name", "").lower()

    if any(kw in name for kw in ("storage", "disk", "flash", "drive")):
        return "mass_storage"
    if any(kw in name for kw in ("keyboard", "mouse", "trackpad", "touch")):
        return "hid"
    if "hub" in name:
        return "hub"
    if any(kw in name for kw in ("audio", "speaker", "microphone")):
        return "audio"
    return "other"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _normalize_vid(hex_id: str) -> str:
    """Normalize a vendor/product ID."""
    return hex_id.lower().removeprefix("0x").zfill(4)


def _get_external_disks() -> list[str]:
    """Get list of external disk identifiers."""
    try:
        result = subprocess.run(
            ["diskutil", "list", "-plist", "external"],
            capture_output=True,
            check=True,
        )
        plist_data = plistlib.loads(result.stdout)
        disks = plist_data.get("AllDisksAndPartitions", [])
        return [d.get("DeviceIdentifier", "") for d in disks if d.get("DeviceIdentifier")]
    except (subprocess.CalledProcessError, plistlib.InvalidFileException):
        return []


def _eject_disk(disk_identifier: str) -> None:
    """Eject a disk by its identifier."""
    subprocess.run(
        ["diskutil", "eject", disk_identifier],
        capture_output=True,
        check=True,
    )
