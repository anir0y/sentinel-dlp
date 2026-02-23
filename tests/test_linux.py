"""Tests for Linux USB management platform layer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dlp.platform.linux import (
    LinuxProgramBlocker,
    LinuxUSBManager,
    _classify_linux,
    _normalize_hex,
    _parse_udevadm_db,
)


# ---------------------------------------------------------------------------
# udevadm output fixtures
# ---------------------------------------------------------------------------

SAMPLE_UDEVADM_DB = """\
P: /devices/pci0000:00/0000:00:14.0/usb1/1-1
E: SUBSYSTEM=usb
E: ID_VENDOR_ID=0781
E: ID_MODEL_ID=5583
E: ID_SERIAL_SHORT=ABC123DEF
E: ID_VENDOR=SanDisk
E: ID_MODEL=Ultra_Fit
E: DRIVER=usb-storage
E: DEVPATH=/devices/pci0000:00/0000:00:14.0/usb1/1-1

P: /devices/pci0000:00/0000:00:14.0/usb1/1-2
E: SUBSYSTEM=usb
E: ID_VENDOR_ID=046d
E: ID_MODEL_ID=c52b
E: ID_SERIAL_SHORT=
E: ID_VENDOR=Logitech
E: ID_MODEL=Unifying_Receiver
E: DRIVER=usbhid
E: DEVPATH=/devices/pci0000:00/0000:00:14.0/usb1/1-2

P: /devices/pci0000:00/0000:00:14.0/usb1
E: SUBSYSTEM=usb
E: DRIVER=hub
E: DEVPATH=/devices/pci0000:00/0000:00:14.0/usb1

P: /devices/platform/sound
E: SUBSYSTEM=sound
E: DRIVER=snd_intel_hda
"""

EMPTY_UDEVADM_DB = ""


# ---------------------------------------------------------------------------
# _parse_udevadm_db tests
# ---------------------------------------------------------------------------


class TestParseUdevadmDb:
    def test_parses_two_usb_devices(self):
        devices = _parse_udevadm_db(SAMPLE_UDEVADM_DB)
        # Hub has no VID/PID from the test data above, but the 2 devices do.
        # Actually the hub block has DRIVER=hub but no ID_VENDOR_ID, so it's skipped.
        assert len(devices) == 2

    def test_sandisk_device(self):
        devices = _parse_udevadm_db(SAMPLE_UDEVADM_DB)
        sandisk = [d for d in devices if d.vendor_id == "0781"]
        assert len(sandisk) == 1
        d = sandisk[0]
        assert d.product_id == "5583"
        assert d.serial_number == "ABC123DEF"
        assert d.manufacturer == "SanDisk"
        assert d.product_name == "Ultra_Fit"
        assert d.device_class == "mass_storage"

    def test_logitech_hid(self):
        devices = _parse_udevadm_db(SAMPLE_UDEVADM_DB)
        logitech = [d for d in devices if d.vendor_id == "046d"]
        assert len(logitech) == 1
        d = logitech[0]
        assert d.product_id == "c52b"
        assert d.device_class == "hid"

    def test_empty_db(self):
        devices = _parse_udevadm_db(EMPTY_UDEVADM_DB)
        assert devices == []

    def test_non_usb_subsystem_skipped(self):
        db = """\
P: /devices/platform/sound
E: SUBSYSTEM=sound
E: DRIVER=snd_intel_hda
"""
        devices = _parse_udevadm_db(db)
        assert devices == []


# ---------------------------------------------------------------------------
# _classify_linux tests
# ---------------------------------------------------------------------------


class TestClassifyLinux:
    def test_hid_by_driver(self):
        assert _classify_linux({"DRIVER": "usbhid"}) == "hid"

    def test_hid_by_interface_class(self):
        assert _classify_linux({"bInterfaceClass": "03"}) == "hid"

    def test_mass_storage_by_driver(self):
        assert _classify_linux({"DRIVER": "usb-storage"}) == "mass_storage"

    def test_mass_storage_by_interface_class(self):
        assert _classify_linux({"bInterfaceClass": "08"}) == "mass_storage"

    def test_hub(self):
        assert _classify_linux({"DRIVER": "hub"}) == "hub"

    def test_audio(self):
        assert _classify_linux({"DRIVER": "snd-usb-audio"}) == "audio"

    def test_other(self):
        assert _classify_linux({"DRIVER": "some_random_driver"}) == "other"


# ---------------------------------------------------------------------------
# _normalize_hex tests
# ---------------------------------------------------------------------------


class TestNormalizeHex:
    def test_lowercase(self):
        assert _normalize_hex("04AB") == "04ab"

    def test_strip_prefix(self):
        assert _normalize_hex("0x046d") == "046d"

    def test_already_clean(self):
        assert _normalize_hex("046d") == "046d"


# ---------------------------------------------------------------------------
# LinuxUSBManager dry-run tests
# ---------------------------------------------------------------------------


class TestLinuxUSBManagerDryRun:
    def test_block_mass_storage_dry_run(self):
        mgr = LinuxUSBManager(dry_run=True)
        assert mgr.is_mass_storage_blocked() is False
        mgr.block_mass_storage()
        assert mgr.is_mass_storage_blocked() is True

    def test_unblock_mass_storage_dry_run(self):
        mgr = LinuxUSBManager(dry_run=True)
        mgr.block_mass_storage()
        mgr.unblock_mass_storage()
        assert mgr.is_mass_storage_blocked() is False

    def test_block_device_dry_run(self):
        mgr = LinuxUSBManager(dry_run=True)
        mgr.block_device("0781", "5583")
        blocked = mgr.get_blocked_devices()
        assert ("0781", "5583") in blocked

    def test_allow_device_dry_run(self):
        mgr = LinuxUSBManager(dry_run=True)
        mgr.block_device("0781", "5583")
        mgr.allow_device("0781", "5583")
        blocked = mgr.get_blocked_devices()
        assert ("0781", "5583") not in blocked

    @patch("dlp.platform.linux.subprocess")
    def test_enumerate_uses_udevadm(self, mock_subprocess):
        mgr = LinuxUSBManager(dry_run=True)

        result = MagicMock()
        result.returncode = 0
        result.stdout = SAMPLE_UDEVADM_DB
        mock_subprocess.run.return_value = result

        devices = mgr.enumerate_devices()
        assert len(devices) == 2
        mock_subprocess.run.assert_called_once()

    @patch("dlp.platform.linux.subprocess")
    def test_enumerate_hid_only(self, mock_subprocess):
        mgr = LinuxUSBManager(dry_run=True)

        result = MagicMock()
        result.returncode = 0
        result.stdout = SAMPLE_UDEVADM_DB
        mock_subprocess.run.return_value = result

        hid_devices = mgr.enumerate_hid_devices()
        assert len(hid_devices) == 1
        assert hid_devices[0].device_class == "hid"


# ---------------------------------------------------------------------------
# LinuxProgramBlocker stub tests
# ---------------------------------------------------------------------------


class TestLinuxProgramBlocker:
    def test_not_available(self):
        blocker = LinuxProgramBlocker()
        assert blocker.is_available() is False

    def test_list_rules_empty(self):
        blocker = LinuxProgramBlocker()
        assert blocker.list_rules() == []

    def test_block_raises(self):
        blocker = LinuxProgramBlocker()
        with pytest.raises(NotImplementedError):
            blocker.block_path("/some/path")


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestLinuxFactory:
    @patch("dlp.platform._platform.system", return_value="Linux")
    def test_get_usb_manager_returns_linux(self, _):
        from dlp.platform import get_usb_manager

        mgr = get_usb_manager(dry_run=True)
        assert isinstance(mgr, LinuxUSBManager)

    @patch("dlp.platform._platform.system", return_value="Linux")
    def test_get_platform_name_linux(self, _):
        from dlp.platform import get_platform_name

        name = get_platform_name()
        assert "Linux" in name
