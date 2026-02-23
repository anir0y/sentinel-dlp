"""Shared test fixtures for DLP TUI tests."""

from __future__ import annotations

import pytest

from dlp.audit.rollback import RollbackJournal
from dlp.config import DLPConfig, WhitelistEntry
from dlp.platform.base import USBDeviceInfo


@pytest.fixture
def sample_usb_device() -> USBDeviceInfo:
    return USBDeviceInfo(
        vendor_id="0781",
        product_id="5583",
        serial_number="ABC123DEF",
        manufacturer="SanDisk",
        product_name="SanDisk Ultra",
        device_class="mass_storage",
        device_path="USB\\VID_0781&PID_5583\\ABC123DEF",
    )


@pytest.fixture
def sample_hid_device() -> USBDeviceInfo:
    return USBDeviceInfo(
        vendor_id="046d",
        product_id="c52b",
        serial_number="",
        manufacturer="Logitech",
        product_name="Logitech Unifying Receiver",
        device_class="hid",
        device_path="USB\\VID_046D&PID_C52B\\0000",
    )


@pytest.fixture
def unknown_vendor_device() -> USBDeviceInfo:
    return USBDeviceInfo(
        vendor_id="dead",
        product_id="beef",
        serial_number="XYZ",
        manufacturer="Unknown",
        product_name="Mystery Device",
        device_class="other",
        device_path="USB\\VID_DEAD&PID_BEEF\\XYZ",
    )


@pytest.fixture
def sample_whitelist() -> list[WhitelistEntry]:
    return [
        WhitelistEntry(vendor_id="0781", product_id="5583", label="SanDisk Ultra"),
        WhitelistEntry(
            vendor_id="0951",
            product_id="1666",
            serial_number="KING123",
            label="Kingston DataTraveler",
        ),
    ]


@pytest.fixture
def sample_config(sample_whitelist: list[WhitelistEntry]) -> DLPConfig:
    return DLPConfig(
        usb={
            "block_mass_storage": False,
            "whitelist_enabled": True,
            "whitelist": sample_whitelist,
        },
        programs={"enabled": False, "blocked_paths": []},
    )


@pytest.fixture
def rollback_journal() -> RollbackJournal:
    return RollbackJournal()


@pytest.fixture
def fake_system_profiler_xml() -> bytes:
    """Minimal SPUSBDataType plist XML for macOS tests."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
  <dict>
    <key>_name</key>
    <string>USB31Bus</string>
    <key>_items</key>
    <array>
      <dict>
        <key>_name</key>
        <string>SanDisk Ultra</string>
        <key>vendor_id</key>
        <string>0x0781  (SanDisk Corp.)</string>
        <key>product_id</key>
        <string>0x5583</string>
        <key>serial_num</key>
        <string>ABC123DEF</string>
        <key>manufacturer</key>
        <string>SanDisk</string>
        <key>location_id</key>
        <string>0x14100000</string>
      </dict>
      <dict>
        <key>_name</key>
        <string>Apple Keyboard</string>
        <key>vendor_id</key>
        <string>0x05ac  (Apple Inc.)</string>
        <key>product_id</key>
        <string>0x024f</string>
        <key>serial_num</key>
        <string></string>
        <key>manufacturer</key>
        <string>Apple Inc.</string>
        <key>location_id</key>
        <string>0x14200000</string>
      </dict>
    </array>
  </dict>
</array>
</plist>"""


@pytest.fixture
def fake_ioreg_output() -> str:
    """Simulated ioreg -p IOUSB -l -w0 output with a Samsung phone and a hub."""
    return """\
+-o Root  <class IORegistryEntry, id 0x100000100, retain 35>
  +-o AppleT8132USBXHCI@01000000  <class AppleT8132USBXHCI, id 0x1000003d6, registered, matched, active, busy 0 (388 ms), retain 44>
  |       "idProduct" = 26723
  |       "bDeviceClass" = 0
  |       "USB Product Name" = "SAMSUNG_Android"
  |       "bDeviceSubClass" = 0
  |       "USB Vendor Name" = "SAMSUNG"
  |       "idVendor" = 1256
  |       "USB Serial Number" = "RZCXA0S25AK"
  +-o AppleT8132USBXHCI@02000000  <class AppleT8132USBXHCI, id 0x1000003b3, registered, matched, active, busy 0 (26 ms), retain 37>
      +-o USB3.1 Hub  <class IOUSBHostDevice, id 0x100000411, registered, matched, active, busy 0 (10 ms), retain 20>
          "idProduct" = 1552
          "bDeviceClass" = 9
          "USB Product Name" = "USB3.1 Hub"
          "bDeviceSubClass" = 0
          "USB Vendor Name" = "VIA Labs, Inc."
          "idVendor" = 8457
          "USB Serial Number" = ""
  +-o AppleT8132USBXHCI@00000000  <class AppleT8132USBXHCI, id 0x1000003ad, registered, matched, active, busy 0 (13 ms), retain 37>
"""


@pytest.fixture
def fake_diskutil_external_plist() -> bytes:
    """Minimal diskutil list -plist external output."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>AllDisksAndPartitions</key>
  <array>
    <dict>
      <key>DeviceIdentifier</key>
      <string>disk4</string>
    </dict>
  </array>
</dict>
</plist>"""
