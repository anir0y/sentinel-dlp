"""HID device viewer screen with vendor fingerprinting."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from dlp.features.hid_fingerprint import DeviceFingerprint
from dlp.ui.widgets.device_table import DeviceTable


class HIDViewerScreen(Static):
    """HID device enumeration and fingerprinting display."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="feature-container"):
            yield Static("HID Device Detection & Vendor Fingerprinting", classes="section-title")
            yield Static("")

            with Horizontal(classes="action-bar"):
                yield Button("Scan Devices", variant="primary", id="btn-scan-hid")
                yield Button("Scan All USB", variant="default", id="btn-scan-all")
                yield Button("Block Selected", variant="error", id="btn-block-hid-device")
                yield Button("Whitelist Selected", variant="success", id="btn-whitelist-hid-device")

            yield Static("", id="hid-scan-status")
            yield DeviceTable(id="hid-table")

            yield Static("")
            yield Static("Device Details", classes="section-title")
            yield Static("Select a device in the table above to see details.", id="hid-details")

    def update_scan_status(self, message: str) -> None:
        widget = self.query_one("#hid-scan-status", Static)
        widget.update(message)

    def load_devices(self, fingerprints: list[DeviceFingerprint]) -> None:
        table = self.query_one("#hid-table", DeviceTable)
        table.load_devices(fingerprints)
        ducky_count = sum(1 for fp in fingerprints if fp.ducky.is_ducky)
        status = f"Found {len(fingerprints)} devices"
        if ducky_count:
            status += f" | [bold red]{ducky_count} POTENTIAL RUBBER DUCKY DETECTED[/]"
        self.update_scan_status(status)

    def show_device_details(self, fp: DeviceFingerprint) -> None:
        widget = self.query_one("#hid-details", Static)
        risk_color = {
            "critical": "reverse red",
            "high": "red",
            "medium": "yellow",
            "low": "green",
            "unknown": "dim",
        }.get(fp.risk_level, "white")

        details = (
            f"Product: {fp.device.product_name}\n"
            f"Manufacturer: {fp.vendor_name} (known: {fp.is_known_vendor})\n"
            f"VID: {fp.device.vendor_id} | PID: {fp.device.product_id}\n"
            f"Serial: {fp.device.serial_number or 'N/A'}\n"
            f"Class: {fp.device.device_class}\n"
            f"Path: {fp.device.device_path}\n"
            f"Risk: [{risk_color}]{fp.risk_level.upper()}[/] - {fp.risk_reason}"
        )

        # Ducky analysis section
        if fp.ducky.is_ducky:
            details += (
                f"\n\n[bold reverse red] RUBBER DUCKY / BadUSB ALERT [/]\n"
                f"  Confidence: {fp.ducky.confidence.upper()}\n"
                f"  Reason: {fp.ducky.reason}"
            )
            if fp.ducky.device_label:
                details += f"\n  Identified as: {fp.ducky.device_label}"
            details += (
                f"\n\n  [bold]Recommended action:[/] Block this device immediately.\n"
                f"  Use USB Manager > Block by VID:PID or disconnect physically."
            )
        elif fp.ducky.confidence != "none" or "suspicious vendor" in fp.ducky.reason.lower():
            details += f"\n\nDucky scan: {fp.ducky.reason}"

        widget.update(details)
