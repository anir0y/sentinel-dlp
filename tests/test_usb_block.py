"""Tests for USB storage blocking (mocked OS calls)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from dlp.platform.darwin import (
    DarwinUSBManager,
    _classify_usb_class,
    _enumerate_via_ioreg,
    _extract_hex,
    _ioreg_node_to_device,
    _walk_usb_tree,
)
from dlp.platform.base import USBDeviceInfo


# --- macOS ioreg tests (primary enumeration) ---


def test_darwin_ioreg_parses_samsung_phone(fake_ioreg_output):
    """ioreg parser should detect a Samsung phone connected via USB."""
    with patch("dlp.platform.darwin.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = fake_ioreg_output
        mock_run.return_value = mock_result
        devices = _enumerate_via_ioreg()

    assert len(devices) == 2

    # Samsung phone
    samsung = devices[0]
    assert samsung.vendor_id == "04e8"
    assert samsung.product_id == "6863"
    assert samsung.serial_number == "RZCXA0S25AK"
    assert samsung.manufacturer == "SAMSUNG"
    assert samsung.product_name == "SAMSUNG_Android"
    assert samsung.device_class == "mass_storage"  # phone classified as storage

    # USB Hub
    hub = devices[1]
    assert hub.vendor_id == "2109"
    assert hub.product_id == "0610"
    assert hub.device_class == "hub"


def test_darwin_ioreg_node_to_device():
    """Test direct conversion of a property dict."""
    props = {
        "idVendor": 1256,
        "idProduct": 26723,
        "USB Product Name": "SAMSUNG_Android",
        "USB Vendor Name": "SAMSUNG",
        "USB Serial Number": "RZCXA0S25AK",
        "bDeviceClass": 0,
    }
    dev = _ioreg_node_to_device(props, "TestNode")
    assert dev.vendor_id == "04e8"
    assert dev.product_id == "6863"
    assert dev.serial_number == "RZCXA0S25AK"
    assert dev.manufacturer == "SAMSUNG"
    assert dev.device_class == "mass_storage"  # Samsung_Android triggers phone heuristic


def test_darwin_enumerate_uses_ioreg_then_fallback(fake_ioreg_output, fake_system_profiler_xml):
    """enumerate_devices should prefer ioreg; only fall back if ioreg returns empty."""
    with patch("dlp.platform.darwin.subprocess.run") as mock_run:
        # ioreg returns devices
        mock_result = MagicMock()
        mock_result.stdout = fake_ioreg_output
        mock_run.return_value = mock_result

        mgr = DarwinUSBManager(dry_run=True)
        devices = mgr.enumerate_devices()

    # Should get ioreg results (2 devices), NOT system_profiler
    assert len(devices) == 2
    assert devices[0].vendor_id == "04e8"  # Samsung from ioreg


def test_darwin_enumerate_fallback_to_system_profiler(fake_system_profiler_xml):
    """If ioreg returns nothing, fall back to system_profiler."""
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: ioreg returns empty
            result = MagicMock()
            result.stdout = "+-o Root  <class IORegistryEntry>\n"
            return result
        else:
            # Second call: system_profiler returns data
            result = MagicMock()
            result.stdout = fake_system_profiler_xml
            return result

    with patch("dlp.platform.darwin.subprocess.run", side_effect=side_effect):
        mgr = DarwinUSBManager(dry_run=True)
        devices = mgr.enumerate_devices()

    assert len(devices) == 2
    assert devices[0].vendor_id == "0781"  # SanDisk from system_profiler


def test_darwin_classify_usb_class():
    """Test USB class code classification."""
    assert _classify_usb_class(8, "") == "mass_storage"
    assert _classify_usb_class(3, "") == "hid"
    assert _classify_usb_class(9, "") == "hub"
    assert _classify_usb_class(1, "") == "audio"
    # Composite device (class 0) uses name heuristics
    assert _classify_usb_class(0, "SAMSUNG_Android") == "mass_storage"
    assert _classify_usb_class(0, "Logitech Keyboard") == "hid"
    assert _classify_usb_class(0, "USB3.1 Hub") == "hub"
    assert _classify_usb_class(0, "Random Thing") == "other"


# --- macOS system_profiler tests (fallback) ---


def test_darwin_system_profiler_parses_xml(fake_system_profiler_xml):
    """Test system_profiler XML parsing still works as fallback."""
    with patch("dlp.platform.darwin.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=fake_system_profiler_xml)
        from dlp.platform.darwin import _enumerate_via_system_profiler
        devices = _enumerate_via_system_profiler()

    assert len(devices) == 2
    assert devices[0].vendor_id == "0781"
    assert devices[0].serial_number == "ABC123DEF"
    assert devices[1].vendor_id == "05ac"


def test_darwin_extract_hex():
    assert _extract_hex("0x0781  (SanDisk Corp.)") == "0781"
    assert _extract_hex("0x05ac") == "05ac"
    assert _extract_hex("0781") == "0781"
    assert _extract_hex("") == "0000"


def test_darwin_block_mass_storage_dry_run():
    mgr = DarwinUSBManager(dry_run=True)
    assert mgr.is_mass_storage_blocked() is False
    mgr.block_mass_storage()
    assert mgr.is_mass_storage_blocked() is True
    mgr.unblock_mass_storage()
    assert mgr.is_mass_storage_blocked() is False


def test_darwin_block_device():
    mgr = DarwinUSBManager(dry_run=True)
    mgr.block_device("0781", "5583")
    assert ("0781", "5583") in mgr.get_blocked_devices()
    mgr.allow_device("0781", "5583")
    assert ("0781", "5583") not in mgr.get_blocked_devices()


def test_darwin_get_external_disks(fake_diskutil_external_plist):
    with patch("dlp.platform.darwin.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=fake_diskutil_external_plist)
        from dlp.platform.darwin import _get_external_disks

        disks = _get_external_disks()
    assert disks == ["disk4"]


# --- Windows tests (mock winreg via sys.modules, run on any platform) ---


@pytest.fixture
def mock_winreg():
    """Inject a mock winreg module into sys.modules for Windows tests."""
    mock = MagicMock()
    mock.HKEY_LOCAL_MACHINE = 0x80000002
    mock.KEY_SET_VALUE = 0x0002
    mock.KEY_READ = 0x20019
    mock.KEY_ALL_ACCESS = 0xF003F
    mock.KEY_WRITE = 0x20006
    mock.REG_DWORD = 4
    mock.REG_SZ = 1

    old = sys.modules.get("winreg")
    sys.modules["winreg"] = mock
    yield mock
    if old is not None:
        sys.modules["winreg"] = old
    else:
        sys.modules.pop("winreg", None)


def test_windows_parse_vid_pid():
    from dlp.platform.windows import _parse_vid_pid

    vid, pid = _parse_vid_pid("USB\\VID_0781&PID_5583\\ABC123")
    assert vid == "0781"
    assert pid == "5583"


def test_windows_parse_vid_pid_no_match():
    from dlp.platform.windows import _parse_vid_pid

    vid, pid = _parse_vid_pid("SOME_RANDOM_STRING")
    assert vid == "0000"
    assert pid == "0000"


def test_windows_extract_serial():
    from dlp.platform.windows import _extract_serial

    assert _extract_serial("USB\\VID_0781&PID_5583\\ABC123") == "ABC123"
    assert _extract_serial("SHORT") == ""


def test_windows_classify_pnp_class():
    from dlp.platform.windows import _classify_pnp_class

    assert _classify_pnp_class("USBSTOR") == "mass_storage"
    assert _classify_pnp_class("HIDClass") == "hid"
    assert _classify_pnp_class("USBHub") == "hub"
    assert _classify_pnp_class(None) == "other"
    assert _classify_pnp_class("SomethingElse") == "other"


def test_windows_block_mass_storage(mock_winreg):
    from dlp.platform.windows import WindowsUSBManager

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value = mock_key

    mgr = WindowsUSBManager(dry_run=False)
    mgr.block_mass_storage()

    mock_winreg.SetValueEx.assert_called_once_with(
        mock_key, "Start", 0, mock_winreg.REG_DWORD, 4
    )
    mock_winreg.CloseKey.assert_called_once_with(mock_key)


def test_windows_unblock_mass_storage(mock_winreg):
    from dlp.platform.windows import WindowsUSBManager

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value = mock_key

    mgr = WindowsUSBManager(dry_run=False)
    mgr.unblock_mass_storage()

    mock_winreg.SetValueEx.assert_called_once_with(
        mock_key, "Start", 0, mock_winreg.REG_DWORD, 3
    )


def test_windows_is_blocked_true(mock_winreg):
    from dlp.platform.windows import WindowsUSBManager

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (4, 1)

    mgr = WindowsUSBManager(dry_run=False)
    assert mgr.is_mass_storage_blocked() is True


def test_windows_is_blocked_false(mock_winreg):
    from dlp.platform.windows import WindowsUSBManager

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (3, 1)

    mgr = WindowsUSBManager(dry_run=False)
    assert mgr.is_mass_storage_blocked() is False


def test_windows_dry_run_does_not_touch_registry():
    """Dry run should not import winreg at all."""
    from dlp.platform.windows import WindowsUSBManager

    mgr = WindowsUSBManager(dry_run=True)
    mgr.block_mass_storage()
    mgr.unblock_mass_storage()
    assert mgr.is_mass_storage_blocked() is False
