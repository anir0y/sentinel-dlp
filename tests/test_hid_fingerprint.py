"""Tests for HID detection, vendor fingerprinting, and rubber ducky detection."""

from __future__ import annotations

from dlp.features.hid_fingerprint import (
    DuckyMatch,
    check_rubber_ducky,
    fingerprint_device,
    fingerprint_devices,
    lookup_vendor,
)
from dlp.platform.base import USBDeviceInfo


# ---------------------------------------------------------------------------
# Vendor lookup tests
# ---------------------------------------------------------------------------


def test_lookup_known_vendor():
    name, is_known = lookup_vendor("046d")
    assert name == "Logitech"
    assert is_known is True


def test_lookup_known_vendor_with_prefix():
    name, is_known = lookup_vendor("0x046d")
    assert name == "Logitech"
    assert is_known is True


def test_lookup_unknown_vendor():
    name, is_known = lookup_vendor("ffff")
    assert name == "Unknown Vendor"
    assert is_known is False


# ---------------------------------------------------------------------------
# Device fingerprinting tests (existing — now also verify ducky field)
# ---------------------------------------------------------------------------


def test_fingerprint_known_hid_device(sample_hid_device):
    fp = fingerprint_device(sample_hid_device)
    assert fp.vendor_name == "Logitech"
    assert fp.is_known_vendor is True
    assert fp.risk_level == "low"
    assert "hid" in fp.risk_reason.lower()
    # Logitech receiver is not a ducky
    assert fp.ducky.is_ducky is False
    assert fp.ducky.confidence == "none"


def test_fingerprint_mass_storage_device(sample_usb_device):
    fp = fingerprint_device(sample_usb_device)
    assert fp.vendor_name == "SanDisk"
    assert fp.is_known_vendor is True
    assert fp.risk_level == "medium"
    assert "mass storage" in fp.risk_reason.lower()
    assert fp.ducky.is_ducky is False


def test_fingerprint_unknown_vendor(unknown_vendor_device):
    fp = fingerprint_device(unknown_vendor_device)
    assert fp.is_known_vendor is False
    assert fp.risk_level == "high"
    assert "unknown vendor" in fp.risk_reason.lower()
    assert fp.ducky.is_ducky is False


def test_fingerprint_hid_with_unknown_manufacturer():
    device = USBDeviceInfo(
        vendor_id="046d",
        product_id="c52b",
        serial_number="",
        manufacturer="Unknown",
        product_name="Some HID",
        device_class="hid",
        device_path="test",
    )
    fp = fingerprint_device(device)
    assert fp.risk_level == "medium"
    assert "no manufacturer" in fp.risk_reason.lower()
    assert fp.ducky.is_ducky is False


def test_fingerprint_devices_batch(sample_hid_device, sample_usb_device, unknown_vendor_device):
    fps = fingerprint_devices([sample_hid_device, sample_usb_device, unknown_vendor_device])
    assert len(fps) == 3
    assert fps[0].risk_level == "low"
    assert fps[1].risk_level == "medium"
    assert fps[2].risk_level == "high"


# ---------------------------------------------------------------------------
# Rubber ducky detection — check_rubber_ducky() direct tests
# ---------------------------------------------------------------------------


def _make_device(
    vid: str = "046d",
    pid: str = "c52b",
    name: str = "Keyboard",
    manufacturer: str = "Logitech",
    device_class: str = "hid",
) -> USBDeviceInfo:
    """Helper to create a USBDeviceInfo with minimal boilerplate."""
    return USBDeviceInfo(
        vendor_id=vid,
        product_id=pid,
        serial_number="",
        manufacturer=manufacturer,
        product_name=name,
        device_class=device_class,
        device_path=f"USB\\VID_{vid}&PID_{pid}\\0000",
    )


def test_ducky_layer1_exact_vid_pid_match():
    """Layer 1: Known malicious VID:PID → confirmed ducky."""
    # Hak5 USB Rubber Ducky (03eb:2401)
    device = _make_device(vid="03eb", pid="2401", name="Generic Keyboard")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "confirmed"
    assert "Hak5 USB Rubber Ducky" in result.device_label
    assert "malicious" in result.reason.lower()


def test_ducky_layer1_bash_bunny():
    """Layer 1: Bash Bunny VID:PID → confirmed."""
    device = _make_device(vid="f000", pid="ff01", name="USB Composite Device")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "confirmed"
    assert "Bash Bunny" in result.device_label


def test_ducky_layer1_omg_cable():
    """Layer 1: O.MG Cable → confirmed."""
    device = _make_device(vid="2e8a", pid="0005", name="USB Device")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "confirmed"
    assert "O.MG" in result.device_label


def test_ducky_layer1_teensy_hid():
    """Layer 1: Teensy in HID mode → confirmed."""
    device = _make_device(vid="16c0", pid="0486", name="USB HID Device")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "confirmed"
    assert "Teensy" in result.device_label


def test_ducky_layer1_rpi_pico_hid():
    """Layer 1: RPi Pico as HID → confirmed."""
    device = _make_device(vid="2e8a", pid="0003", name="RP2040 HID")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "confirmed"
    assert "Pico" in result.device_label


def test_ducky_layer1_with_hex_prefix():
    """Layer 1 should work with 0x-prefixed VID/PID."""
    device = _make_device(vid="0x03eb", pid="0x2401", name="Keyboard")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "confirmed"


def test_ducky_layer2_product_name_keyword():
    """Layer 2: Product name contains ducky keyword → high confidence."""
    device = _make_device(vid="1234", pid="5678", name="My Rubber Ducky Device")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "high"
    assert "rubber ducky" in result.reason.lower()


def test_ducky_layer2_manufacturer_keyword():
    """Layer 2: Manufacturer name contains ducky keyword → high confidence."""
    device = _make_device(
        vid="1234", pid="5678", name="USB Keyboard", manufacturer="BadUSB Corp"
    )
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "high"
    assert "badusb" in result.reason.lower()


def test_ducky_layer2_digispark_keyword():
    """Layer 2: Digispark in product name → high confidence."""
    device = _make_device(vid="aaaa", pid="bbbb", name="Digispark Pro")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "high"


def test_ducky_layer2_teensy_keyword():
    """Layer 2: Teensy in product name → high confidence (even without VID match)."""
    device = _make_device(vid="aaaa", pid="bbbb", name="Teensy 4.1")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "high"


def test_ducky_layer3_suspicious_vid_hid():
    """Layer 3: Suspicious VID + HID class → medium confidence."""
    # VID 2341 (Arduino) is suspicious but not in KNOWN_DUCKY_DEVICES
    device = _make_device(vid="2341", pid="9999", name="Arduino Board", device_class="hid")
    result = check_rubber_ducky(device)
    assert result.is_ducky is True
    assert result.confidence == "medium"
    assert "suspicious vendor" in result.reason.lower()


def test_ducky_layer3b_suspicious_vid_non_hid():
    """Layer 3b: Suspicious VID but NOT HID class → not flagged, just noted."""
    device = _make_device(vid="2341", pid="9999", name="Arduino Board", device_class="other")
    result = check_rubber_ducky(device)
    assert result.is_ducky is False
    assert result.confidence == "none"
    assert "monitor" in result.reason.lower()


def test_ducky_clean_device():
    """Normal device → no ducky indicators."""
    device = _make_device(vid="046d", pid="c52b", name="Logitech Keyboard")
    result = check_rubber_ducky(device)
    assert result.is_ducky is False
    assert result.confidence == "none"
    assert "no ducky" in result.reason.lower()


def test_ducky_layer1_overrides_layer2():
    """Layer 1 (exact VID:PID) takes priority over layer 2 (keyword)."""
    # This device matches both: VID:PID is in KNOWN_DUCKY_DEVICES AND name has "ducky"
    device = _make_device(vid="03eb", pid="2401", name="My Rubber Ducky Thing")
    result = check_rubber_ducky(device)
    # Should be "confirmed" (layer 1), not "high" (layer 2)
    assert result.confidence == "confirmed"
    assert result.device_label != ""  # Layer 1 sets device_label


# ---------------------------------------------------------------------------
# Risk assessment integration with ducky detection
# ---------------------------------------------------------------------------


def test_fingerprint_confirmed_ducky_is_critical():
    """Confirmed rubber ducky → risk level 'critical'."""
    device = _make_device(vid="03eb", pid="2401", name="Generic Keyboard")
    fp = fingerprint_device(device)
    assert fp.risk_level == "critical"
    assert "RUBBER DUCKY" in fp.risk_reason.upper()
    assert fp.ducky.is_ducky is True
    assert fp.ducky.confidence == "confirmed"


def test_fingerprint_high_confidence_ducky_is_critical():
    """High-confidence ducky (keyword match) → risk level 'critical'."""
    device = _make_device(vid="1234", pid="5678", name="BadUSB Keyboard")
    fp = fingerprint_device(device)
    assert fp.risk_level == "critical"
    assert fp.ducky.is_ducky is True
    assert fp.ducky.confidence == "high"


def test_fingerprint_medium_confidence_ducky_is_high():
    """Medium-confidence ducky (suspicious VID) → risk level 'high'."""
    device = _make_device(vid="2341", pid="9999", name="Arduino Board", device_class="hid")
    fp = fingerprint_device(device)
    assert fp.risk_level == "high"
    assert "suspicious" in fp.risk_reason.lower()
    assert fp.ducky.is_ducky is True
    assert fp.ducky.confidence == "medium"


def test_fingerprint_ducky_overrides_unknown_vendor():
    """Ducky detection should take priority over 'unknown vendor' risk."""
    # VID "f000" is not in VENDOR_DB → would normally be "high: unknown vendor"
    # But it's Bash Bunny → should be "critical"
    device = _make_device(vid="f000", pid="ff01", name="USB Device")
    fp = fingerprint_device(device)
    assert fp.risk_level == "critical"
    assert "RUBBER DUCKY" in fp.risk_reason.upper() or "malicious" in fp.risk_reason.lower()
    assert fp.ducky.is_ducky is True
    assert fp.ducky.confidence == "confirmed"
