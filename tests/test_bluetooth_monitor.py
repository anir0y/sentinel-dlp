"""Tests for Bluetooth device enumeration and classification."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from dlp.features.bluetooth_monitor import _classify_bt_device

# The plist walker expects device_connected to be a list of dicts
# where each dict has device-name-as-key → info-dict-as-value.
SAMPLE_PLIST_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
  <dict>
    <key>device_connected</key>
    <array>
      <dict>
        <key>AirPods Pro</key>
        <dict>
          <key>device_address</key>
          <string>AA-BB-CC-DD-EE-FF</string>
          <key>device_minorType</key>
          <string>Headphones</string>
        </dict>
      </dict>
    </array>
  </dict>
</array>
</plist>
"""

EMPTY_PLIST_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<array>
  <dict>
    <key>device_connected</key>
    <array/>
  </dict>
</array>
</plist>
"""


class TestEnumerateDarwin:
    """Tests for Bluetooth device enumeration on macOS."""

    @patch("dlp.features.bluetooth_monitor.subprocess")
    @patch("dlp.features.bluetooth_monitor.platform")
    def test_enumerate_darwin_parses_plist(self, mock_platform, mock_subprocess):
        from dlp.features.bluetooth_monitor import enumerate_bluetooth_devices

        mock_platform.system.return_value = "Darwin"

        result = MagicMock()
        result.stdout = SAMPLE_PLIST_XML
        result.returncode = 0
        mock_subprocess.run.return_value = result
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        devices = enumerate_bluetooth_devices()
        assert len(devices) >= 1

        names = [d.name for d in devices]
        assert any("AirPods" in n for n in names)

    @patch("dlp.features.bluetooth_monitor.subprocess")
    @patch("dlp.features.bluetooth_monitor.platform")
    def test_enumerate_darwin_empty(self, mock_platform, mock_subprocess):
        from dlp.features.bluetooth_monitor import enumerate_bluetooth_devices

        mock_platform.system.return_value = "Darwin"

        result = MagicMock()
        result.stdout = EMPTY_PLIST_XML
        result.returncode = 0
        mock_subprocess.run.return_value = result
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        devices = enumerate_bluetooth_devices()
        assert devices == []

    @patch("dlp.features.bluetooth_monitor.subprocess")
    @patch("dlp.features.bluetooth_monitor.platform")
    def test_enumerate_darwin_error(self, mock_platform, mock_subprocess):
        from dlp.features.bluetooth_monitor import enumerate_bluetooth_devices

        mock_platform.system.return_value = "Darwin"
        mock_subprocess.run.side_effect = subprocess.CalledProcessError(
            1, "system_profiler"
        )
        mock_subprocess.CalledProcessError = subprocess.CalledProcessError

        devices = enumerate_bluetooth_devices()
        assert devices == []


class TestClassifyBtDevice:
    """Tests for Bluetooth device classification via _classify_bt_device."""

    def test_classify_audio(self):
        result = _classify_bt_device({"device_minorType": "Headphones"})
        assert result == "audio"

    def test_classify_input(self):
        result = _classify_bt_device({"device_minorType": "Keyboard"})
        assert result == "input"

    def test_classify_unknown(self):
        result = _classify_bt_device({"device_minorType": "SomeWeirdThing"})
        assert result == "unknown"

    def test_classify_by_name(self):
        result = _classify_bt_device({"name": "AirPods Pro"})
        assert result == "audio"

    def test_classify_phone(self):
        result = _classify_bt_device({"name": "iPhone 15"})
        assert result == "phone"

    def test_classify_computer(self):
        result = _classify_bt_device({"name": "MacBook Pro"})
        assert result == "computer"
