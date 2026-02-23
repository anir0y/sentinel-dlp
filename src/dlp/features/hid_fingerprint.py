"""HID device detection, vendor fingerprinting, and rubber ducky detection."""

from __future__ import annotations

from dataclasses import dataclass

from dlp.constants import (
    DUCKY_NAME_KEYWORDS,
    KNOWN_DUCKY_DEVICES,
    SUSPICIOUS_HID_VIDS,
    VENDOR_DB,
)
from dlp.platform.base import USBDeviceInfo


@dataclass(frozen=True)
class DuckyMatch:
    """Result of rubber ducky / BadUSB analysis."""

    is_ducky: bool
    confidence: str  # "confirmed", "high", "medium", "none"
    reason: str
    device_label: str  # Known device name if matched, else ""


@dataclass(frozen=True)
class DeviceFingerprint:
    """Enriched device info with vendor fingerprinting and ducky detection."""

    device: USBDeviceInfo
    vendor_name: str
    is_known_vendor: bool
    risk_level: str  # "critical", "high", "medium", "low", "unknown"
    risk_reason: str
    ducky: DuckyMatch


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lookup_vendor(vendor_id: str) -> tuple[str, bool]:
    """Look up vendor name from the built-in database.

    Returns (vendor_name, is_known).
    """
    vid = vendor_id.lower().removeprefix("0x").zfill(4)
    name = VENDOR_DB.get(vid)
    if name:
        return name, True
    return "Unknown Vendor", False


def check_rubber_ducky(device: USBDeviceInfo) -> DuckyMatch:
    """Analyze a USB device for rubber ducky / BadUSB indicators.

    Detection layers (in priority order):
    1. Exact VID:PID match against known malicious device database.
    2. Product name / manufacturer keyword match.
    3. Suspicious VID + HID class heuristic.
    """
    vid = device.vendor_id.lower().removeprefix("0x").zfill(4)
    pid = device.product_id.lower().removeprefix("0x").zfill(4)
    vid_pid_key = f"{vid}:{pid}"

    # Layer 1: exact VID:PID match — confirmed ducky
    if vid_pid_key in KNOWN_DUCKY_DEVICES:
        label, threat = KNOWN_DUCKY_DEVICES[vid_pid_key]
        return DuckyMatch(
            is_ducky=True,
            confidence="confirmed",
            reason=f"Known malicious device: {threat}",
            device_label=label,
        )

    # Layer 2: product name / manufacturer keyword match
    searchable = f"{device.product_name} {device.manufacturer}".lower()
    for keyword in DUCKY_NAME_KEYWORDS:
        if keyword in searchable:
            return DuckyMatch(
                is_ducky=True,
                confidence="high",
                reason=f"Product/manufacturer name contains '{keyword}'",
                device_label="",
            )

    # Layer 3: suspicious VID + HID class
    if vid in SUSPICIOUS_HID_VIDS and device.device_class == "hid":
        return DuckyMatch(
            is_ducky=True,
            confidence="medium",
            reason=f"HID device from suspicious vendor (VID {vid})",
            device_label="",
        )

    # Layer 3b: suspicious VID but not HID class — note but don't flag
    if vid in SUSPICIOUS_HID_VIDS:
        return DuckyMatch(
            is_ducky=False,
            confidence="none",
            reason=f"Non-HID device from suspicious vendor (VID {vid}) — monitor",
            device_label="",
        )

    return DuckyMatch(
        is_ducky=False,
        confidence="none",
        reason="No ducky indicators",
        device_label="",
    )


def fingerprint_device(device: USBDeviceInfo) -> DeviceFingerprint:
    """Fingerprint a USB device and assess risk level."""
    vendor_name, is_known = lookup_vendor(device.vendor_id)
    ducky = check_rubber_ducky(device)
    risk_level, risk_reason = _assess_risk(device, is_known, ducky)

    return DeviceFingerprint(
        device=device,
        vendor_name=vendor_name,
        is_known_vendor=is_known,
        risk_level=risk_level,
        risk_reason=risk_reason,
        ducky=ducky,
    )


def fingerprint_devices(
    devices: list[USBDeviceInfo],
) -> list[DeviceFingerprint]:
    """Fingerprint a list of devices."""
    return [fingerprint_device(d) for d in devices]


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _assess_risk(
    device: USBDeviceInfo, is_known: bool, ducky: DuckyMatch
) -> tuple[str, str]:
    """Assess risk level of a device based on its characteristics.

    Returns (risk_level, reason).
    Priority: ducky detection > unknown vendor > mass storage > HID anomalies > normal.
    """
    # Rubber ducky / BadUSB — highest priority
    if ducky.is_ducky and ducky.confidence == "confirmed":
        label = f" ({ducky.device_label})" if ducky.device_label else ""
        return "critical", f"RUBBER DUCKY DETECTED{label}: {ducky.reason}"

    if ducky.is_ducky and ducky.confidence == "high":
        return "critical", f"Probable BadUSB device: {ducky.reason}"

    if ducky.is_ducky and ducky.confidence == "medium":
        return "high", f"Suspicious HID device: {ducky.reason}"

    # Unknown vendors are suspicious
    if not is_known:
        return "high", "Unknown vendor ID"

    # Mass storage devices carry data exfiltration risk
    if device.device_class == "mass_storage":
        return "medium", "Mass storage device (data exfiltration risk)"

    # HID devices with unknown manufacturer strings
    if device.device_class == "hid" and device.manufacturer == "Unknown":
        return "medium", "HID device with no manufacturer string"

    # Known vendor, non-storage = generally safe
    if device.device_class in ("hid", "hub"):
        return "low", f"Known {device.device_class} device"

    return "unknown", "Unclassified device type"
