"""Linux USB management via udevadm and udev rules."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

from dlp.platform.base import BlockRule, ProgramBlockerBase, USBDeviceInfo, USBManagerBase

logger = logging.getLogger(__name__)

_UDEV_RULES_DIR = Path("/etc/udev/rules.d")
_DLP_BLOCK_ALL_RULE = _UDEV_RULES_DIR / "99-dlp-block-mass-storage.rules"
_DLP_DEVICE_RULES_PREFIX = "99-dlp-block-"


# ---------------------------------------------------------------------------
# USB Manager
# ---------------------------------------------------------------------------


class LinuxUSBManager(USBManagerBase):
    """Linux USB management using udevadm for enumeration and udev rules for blocking."""

    def __init__(self, dry_run: bool = False) -> None:
        super().__init__(dry_run=dry_run)
        self._blocked_devices: list[tuple[str, str]] = []
        self._storage_blocked = False

    def enumerate_devices(self) -> list[USBDeviceInfo]:
        """Enumerate USB devices via ``udevadm info --export-db``."""
        try:
            result = subprocess.run(
                ["udevadm", "info", "--export-db"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                logger.warning("udevadm returned %d", result.returncode)
                return []
            return _parse_udevadm_db(result.stdout)
        except FileNotFoundError:
            logger.warning("udevadm not found")
            return []
        except Exception:
            logger.debug("udevadm enumeration failed", exc_info=True)
            return []

    def enumerate_hid_devices(self) -> list[USBDeviceInfo]:
        """Return only HID-class devices."""
        return [d for d in self.enumerate_devices() if d.device_class == "hid"]

    def block_mass_storage(self) -> None:
        """Block USB mass storage via udev rule."""
        if self.dry_run:
            self._storage_blocked = True
            logger.info("[DRY RUN] Would write udev rule to block mass storage")
            return

        rule_content = (
            '# DLP TUI - Block USB mass storage\n'
            'ACTION=="add", SUBSYSTEMS=="usb", ATTRS{bInterfaceClass}=="08", '
            'RUN+="/bin/sh -c \'echo 0 > /sys/$devpath/authorized\'"\n'
        )
        try:
            _DLP_BLOCK_ALL_RULE.write_text(rule_content)
            _reload_udev_rules()
            self._storage_blocked = True
        except PermissionError:
            logger.error("Permission denied writing udev rule (need root)")
            raise

    def unblock_mass_storage(self) -> None:
        """Remove the mass storage blocking udev rule."""
        if self.dry_run:
            self._storage_blocked = False
            logger.info("[DRY RUN] Would remove mass storage udev rule")
            return

        try:
            if _DLP_BLOCK_ALL_RULE.exists():
                _DLP_BLOCK_ALL_RULE.unlink()
                _reload_udev_rules()
            self._storage_blocked = False
        except PermissionError:
            logger.error("Permission denied removing udev rule (need root)")
            raise

    def is_mass_storage_blocked(self) -> bool:
        """Check if the DLP mass storage block rule exists."""
        if self.dry_run:
            return self._storage_blocked
        return _DLP_BLOCK_ALL_RULE.exists()

    def block_device(self, vendor_id: str, product_id: str) -> None:
        """Block a specific device by VID/PID via udev rule."""
        vid = _normalize_hex(vendor_id)
        pid = _normalize_hex(product_id)

        if self.dry_run:
            self._blocked_devices.append((vid, pid))
            logger.info("[DRY RUN] Would block device %s:%s", vid, pid)
            return

        rule_file = _UDEV_RULES_DIR / f"{_DLP_DEVICE_RULES_PREFIX}{vid}-{pid}.rules"
        rule_content = (
            f'# DLP TUI - Block device {vid}:{pid}\n'
            f'ACTION=="add", ATTRS{{idVendor}}=="{vid}", ATTRS{{idProduct}}=="{pid}", '
            f'RUN+="/bin/sh -c \'echo 0 > /sys/$devpath/authorized\'"\n'
        )
        try:
            rule_file.write_text(rule_content)
            _reload_udev_rules()
            self._blocked_devices.append((vid, pid))
        except PermissionError:
            logger.error("Permission denied writing udev rule (need root)")
            raise

    def allow_device(self, vendor_id: str, product_id: str) -> None:
        """Remove a per-device udev blocking rule."""
        vid = _normalize_hex(vendor_id)
        pid = _normalize_hex(product_id)

        if self.dry_run:
            self._blocked_devices = [(v, p) for v, p in self._blocked_devices if not (v == vid and p == pid)]
            logger.info("[DRY RUN] Would unblock device %s:%s", vid, pid)
            return

        rule_file = _UDEV_RULES_DIR / f"{_DLP_DEVICE_RULES_PREFIX}{vid}-{pid}.rules"
        try:
            if rule_file.exists():
                rule_file.unlink()
                _reload_udev_rules()
            self._blocked_devices = [(v, p) for v, p in self._blocked_devices if not (v == vid and p == pid)]
        except PermissionError:
            logger.error("Permission denied removing udev rule (need root)")
            raise

    def get_blocked_devices(self) -> list[tuple[str, str]]:
        """Return list of (vid, pid) blocked by DLP udev rules."""
        if self.dry_run:
            return list(self._blocked_devices)

        blocked: list[tuple[str, str]] = []
        if not _UDEV_RULES_DIR.exists():
            return blocked
        for rule_file in _UDEV_RULES_DIR.glob(f"{_DLP_DEVICE_RULES_PREFIX}*.rules"):
            stem = rule_file.stem.replace(_DLP_DEVICE_RULES_PREFIX, "")
            parts = stem.split("-")
            if len(parts) == 2:
                blocked.append((parts[0], parts[1]))
        return blocked


# ---------------------------------------------------------------------------
# Program Blocker (stub — not available on Linux)
# ---------------------------------------------------------------------------


class LinuxProgramBlocker(ProgramBlockerBase):
    """Stub program blocker — not available on Linux."""

    def block_path(self, path_pattern: str, description: str = "") -> str:
        raise NotImplementedError("Program blocking not available on Linux")

    def unblock_path(self, rule_id: str) -> None:
        raise NotImplementedError("Program blocking not available on Linux")

    def list_rules(self) -> list[BlockRule]:
        return []

    def is_available(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_hex(value: str) -> str:
    """Strip 0x prefix and lowercase a hex string."""
    return value.lower().removeprefix("0x")


def _reload_udev_rules() -> None:
    """Reload udev rules and trigger."""
    try:
        subprocess.run(
            ["udevadm", "control", "--reload-rules"],
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["udevadm", "trigger"],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        logger.debug("Failed to reload udev rules", exc_info=True)


def _parse_udevadm_db(output: str) -> list[USBDeviceInfo]:
    """Parse ``udevadm info --export-db`` output into USBDeviceInfo list.

    The output is a series of device blocks separated by blank lines.
    Each block starts with ``P:`` (syspath) and has ``E:`` lines for properties.
    We only care about blocks that have SUBSYSTEM=usb and ID_VENDOR_ID set.
    """
    devices: list[USBDeviceInfo] = []
    blocks = output.split("\n\n")

    for block in blocks:
        if not block.strip():
            continue

        props: dict[str, str] = {}
        devpath = ""

        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("P: "):
                devpath = line[3:]
            elif line.startswith("E: "):
                key_val = line[3:]
                if "=" in key_val:
                    key, _, val = key_val.partition("=")
                    props[key] = val

        # Only USB devices with vendor/product IDs
        subsystem = props.get("SUBSYSTEM", "")
        if subsystem != "usb":
            continue

        vid = props.get("ID_VENDOR_ID", "")
        pid = props.get("ID_MODEL_ID", "")
        if not vid or not pid:
            continue

        device_class = _classify_linux(props)
        devices.append(
            USBDeviceInfo(
                vendor_id=vid,
                product_id=pid,
                serial_number=props.get("ID_SERIAL_SHORT", ""),
                manufacturer=props.get("ID_VENDOR", "Unknown"),
                product_name=props.get("ID_MODEL", "Unknown USB Device"),
                device_class=device_class,
                device_path=devpath or props.get("DEVPATH", ""),
            )
        )

    return devices


def _classify_linux(props: dict[str, str]) -> str:
    """Classify a Linux USB device based on its udev properties."""
    driver = props.get("DRIVER", "").lower()
    iface_class = props.get("bInterfaceClass", "")

    # HID
    if driver in ("usbhid", "hid-generic") or iface_class == "03":
        return "hid"

    # Mass storage
    if driver in ("usb-storage", "uas") or iface_class == "08":
        return "mass_storage"

    # Hub
    if driver == "hub" or iface_class == "09":
        return "hub"

    # Audio
    if driver in ("snd-usb-audio",) or iface_class == "01":
        return "audio"

    return "other"
