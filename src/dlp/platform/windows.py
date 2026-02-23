"""Windows platform implementation using winreg, WMI, and SRP."""

from __future__ import annotations

import logging
import re
import uuid

from dlp.constants import (
    DEVICE_INSTALL_RESTRICTIONS_PATH,
    SRP_CODE_IDENTIFIERS_PATH,
    USBSTOR_DISABLED,
    USBSTOR_ENABLED,
    USBSTOR_KEY_PATH,
)
from dlp.platform.base import BlockRule, ProgramBlockerBase, USBDeviceInfo, USBManagerBase

logger = logging.getLogger(__name__)


class WindowsUSBManager(USBManagerBase):
    """Windows USB management via winreg and WMI."""

    def enumerate_devices(self) -> list[USBDeviceInfo]:
        from dlp.errors import USBEnumerationError

        try:
            import wmi
        except ImportError as e:
            raise USBEnumerationError("WMI module not available") from e

        try:
            c = wmi.WMI()
            devices: list[USBDeviceInfo] = []
            for entity in c.Win32_PnPEntity():
                did = entity.DeviceID or ""
                if not did.startswith("USB"):
                    continue
                vid, pid = _parse_vid_pid(did)
                devices.append(
                    USBDeviceInfo(
                        vendor_id=vid,
                        product_id=pid,
                        serial_number=_extract_serial(did),
                        manufacturer=entity.Manufacturer or "Unknown",
                        product_name=entity.Name or "Unknown",
                        device_class=_classify_pnp_class(entity.PNPClass),
                        device_path=did,
                    )
                )
            return devices
        except USBEnumerationError:
            raise
        except Exception as e:
            raise USBEnumerationError(f"WMI enumeration failed: {e}") from e

    def enumerate_hid_devices(self) -> list[USBDeviceInfo]:
        import wmi

        c = wmi.WMI()
        devices: list[USBDeviceInfo] = []
        for entity in c.Win32_PnPEntity(PNPClass="HIDClass"):
            did = entity.DeviceID or ""
            vid, pid = _parse_vid_pid(did)
            devices.append(
                USBDeviceInfo(
                    vendor_id=vid,
                    product_id=pid,
                    serial_number=_extract_serial(did),
                    manufacturer=entity.Manufacturer or "Unknown",
                    product_name=entity.Name or "Unknown",
                    device_class="hid",
                    device_path=did,
                )
            )
        return devices

    def block_mass_storage(self) -> None:
        if self.dry_run:
            logger.info("[DRY RUN] Would set USBSTOR Start=%d", USBSTOR_DISABLED)
            return
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            USBSTOR_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, USBSTOR_DISABLED)
        finally:
            winreg.CloseKey(key)
        logger.info("USBSTOR Start set to %d (disabled)", USBSTOR_DISABLED)

    def unblock_mass_storage(self) -> None:
        if self.dry_run:
            logger.info("[DRY RUN] Would set USBSTOR Start=%d", USBSTOR_ENABLED)
            return
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            USBSTOR_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, USBSTOR_ENABLED)
        finally:
            winreg.CloseKey(key)
        logger.info("USBSTOR Start set to %d (enabled)", USBSTOR_ENABLED)

    def is_mass_storage_blocked(self) -> bool:
        if self.dry_run:
            return False
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            USBSTOR_KEY_PATH,
            0,
            winreg.KEY_READ,
        )
        try:
            value, _ = winreg.QueryValueEx(key, "Start")
        finally:
            winreg.CloseKey(key)
        return value == USBSTOR_DISABLED

    def block_device(self, vendor_id: str, product_id: str) -> None:
        hw_id = f"USB\\VID_{vendor_id}&PID_{product_id}"
        if self.dry_run:
            logger.info("[DRY RUN] Would add %s to device deny list", hw_id)
            return
        import winreg

        deny_path = f"{DEVICE_INSTALL_RESTRICTIONS_PATH}\\DenyDeviceIDs"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, deny_path, 0, winreg.KEY_ALL_ACCESS
            )
        except FileNotFoundError:
            key = winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, deny_path, 0, winreg.KEY_ALL_ACCESS
            )
        try:
            idx = _next_deny_index(key)
            winreg.SetValueEx(key, str(idx), 0, winreg.REG_SZ, hw_id)
        finally:
            winreg.CloseKey(key)

        # Enable deny policy
        _set_restriction_flag("DenyDeviceIDs", 1)
        logger.info("Added %s to device deny list", hw_id)

    def allow_device(self, vendor_id: str, product_id: str) -> None:
        hw_id = f"USB\\VID_{vendor_id}&PID_{product_id}"
        if self.dry_run:
            logger.info("[DRY RUN] Would add %s to device allow list", hw_id)
            return
        import winreg

        allow_path = f"{DEVICE_INSTALL_RESTRICTIONS_PATH}\\AllowDeviceIDs"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, allow_path, 0, winreg.KEY_ALL_ACCESS
            )
        except FileNotFoundError:
            key = winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, allow_path, 0, winreg.KEY_ALL_ACCESS
            )
        try:
            idx = _next_deny_index(key)
            winreg.SetValueEx(key, str(idx), 0, winreg.REG_SZ, hw_id)
        finally:
            winreg.CloseKey(key)

        _set_restriction_flag("AllowDeviceIDs", 1)
        logger.info("Added %s to device allow list", hw_id)

    def get_blocked_devices(self) -> list[tuple[str, str]]:
        if self.dry_run:
            return []
        import winreg

        deny_path = f"{DEVICE_INSTALL_RESTRICTIONS_PATH}\\DenyDeviceIDs"
        blocked: list[tuple[str, str]] = []
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, deny_path, 0, winreg.KEY_READ
            )
        except FileNotFoundError:
            return blocked
        try:
            i = 0
            while True:
                try:
                    _, value, _ = winreg.EnumValue(key, i)
                    vid, pid = _parse_vid_pid(value)
                    if vid != "0000":
                        blocked.append((vid, pid))
                    i += 1
                except OSError:
                    break
        finally:
            winreg.CloseKey(key)
        return blocked


class WindowsProgramBlocker(ProgramBlockerBase):
    """Program blocking via Software Restriction Policies."""

    def block_path(self, path_pattern: str, description: str = "") -> str:
        rule_guid = str(uuid.uuid4())
        if self.dry_run:
            logger.info("[DRY RUN] Would create SRP rule %s for %s", rule_guid, path_pattern)
            return rule_guid
        import winreg

        key_path = f"{SRP_CODE_IDENTIFIERS_PATH}\\0\\Paths\\{{{rule_guid}}}"
        key = winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE
        )
        try:
            winreg.SetValueEx(key, "ItemData", 0, winreg.REG_SZ, path_pattern)
            winreg.SetValueEx(key, "SaferFlags", 0, winreg.REG_DWORD, 0)
            if description:
                winreg.SetValueEx(key, "Description", 0, winreg.REG_SZ, description)
        finally:
            winreg.CloseKey(key)
        logger.info("Created SRP path rule %s: %s", rule_guid, path_pattern)
        return rule_guid

    def unblock_path(self, rule_id: str) -> None:
        if self.dry_run:
            logger.info("[DRY RUN] Would delete SRP rule %s", rule_id)
            return
        import winreg

        key_path = f"{SRP_CODE_IDENTIFIERS_PATH}\\0\\Paths\\{{{rule_id}}}"
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        logger.info("Deleted SRP path rule %s", rule_id)

    def list_rules(self) -> list[BlockRule]:
        if self.dry_run:
            return []
        import winreg

        rules: list[BlockRule] = []
        paths_key_path = f"{SRP_CODE_IDENTIFIERS_PATH}\\0\\Paths"
        try:
            paths_key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, paths_key_path, 0, winreg.KEY_READ
            )
        except FileNotFoundError:
            return rules
        try:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(paths_key, i)
                    subkey = winreg.OpenKey(paths_key, subkey_name, 0, winreg.KEY_READ)
                    try:
                        item_data, _ = winreg.QueryValueEx(subkey, "ItemData")
                        desc = ""
                        try:
                            desc, _ = winreg.QueryValueEx(subkey, "Description")
                        except FileNotFoundError:
                            pass
                        rule_id = subkey_name.strip("{}")
                        rules.append(BlockRule(
                            rule_id=rule_id,
                            path_pattern=item_data,
                            description=desc,
                        ))
                    finally:
                        winreg.CloseKey(subkey)
                    i += 1
                except OSError:
                    break
        finally:
            winreg.CloseKey(paths_key)
        return rules

    def is_available(self) -> bool:
        """SRP is available on all Windows editions."""
        import platform as _platform

        return _platform.system() == "Windows"


# --- Helper functions ---


def _parse_vid_pid(device_id: str) -> tuple[str, str]:
    """Extract VID and PID from a Windows device ID string."""
    vid_match = re.search(r"VID_([0-9A-Fa-f]{4})", device_id)
    pid_match = re.search(r"PID_([0-9A-Fa-f]{4})", device_id)
    return (
        vid_match.group(1) if vid_match else "0000",
        pid_match.group(1) if pid_match else "0000",
    )


def _extract_serial(device_id: str) -> str:
    """Extract serial number from a Windows device ID (last segment after \\)."""
    parts = device_id.split("\\")
    if len(parts) >= 3:
        return parts[-1]
    return ""


def _classify_pnp_class(pnp_class: str | None) -> str:
    """Map Windows PNP class to our device class."""
    if not pnp_class:
        return "other"
    mapping = {
        "USB": "other",
        "USBSTOR": "mass_storage",
        "HIDClass": "hid",
        "USBHub": "hub",
        "MEDIA": "audio",
        "AudioEndpoint": "audio",
    }
    return mapping.get(pnp_class, "other")


def _next_deny_index(key) -> int:
    """Find the next available numeric index in a deny/allow subkey."""
    import winreg

    max_idx = 0
    i = 0
    while True:
        try:
            name, _, _ = winreg.EnumValue(key, i)
            try:
                idx = int(name)
                max_idx = max(max_idx, idx)
            except ValueError:
                pass
            i += 1
        except OSError:
            break
    return max_idx + 1


def _set_restriction_flag(flag_name: str, value: int) -> None:
    """Set a top-level restriction flag in the DeviceInstall\\Restrictions key."""
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        DEVICE_INSTALL_RESTRICTIONS_PATH,
        0,
        winreg.KEY_SET_VALUE,
    )
    try:
        winreg.SetValueEx(key, flag_name, 0, winreg.REG_DWORD, value)
    finally:
        winreg.CloseKey(key)
