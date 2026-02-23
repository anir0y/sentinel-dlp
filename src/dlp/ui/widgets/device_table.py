"""Reusable DataTable widget for USB/HID devices."""

from __future__ import annotations

from textual.widgets import DataTable

from dlp.features.hid_fingerprint import DeviceFingerprint


class DeviceTable(DataTable):
    """DataTable pre-configured for displaying USB device information."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._fingerprints: dict[str, DeviceFingerprint] = {}
        self._ordered_keys: list[str] = []

    def on_mount(self) -> None:
        self.add_columns(
            "Vendor ID",
            "Product ID",
            "Manufacturer",
            "Product",
            "Class",
            "Serial",
            "Ducky?",
            "Risk",
        )

    def load_devices(self, fingerprints: list[DeviceFingerprint]) -> None:
        """Clear and reload the table with fingerprinted devices."""
        self.clear()
        self._fingerprints.clear()
        self._ordered_keys.clear()
        for fp in fingerprints:
            key = fp.device.device_path
            self._fingerprints[key] = fp
            self._ordered_keys.append(key)
            risk_display = _format_risk(fp.risk_level)
            ducky_display = _format_ducky(fp)
            self.add_row(
                fp.device.vendor_id,
                fp.device.product_id,
                fp.vendor_name,
                fp.device.product_name,
                fp.device.device_class,
                fp.device.serial_number or "-",
                ducky_display,
                risk_display,
                key=key,
            )

    def get_selected_fingerprint(self) -> DeviceFingerprint | None:
        """Return the DeviceFingerprint for the currently highlighted row."""
        if self.cursor_row is not None and 0 <= self.cursor_row < len(self._ordered_keys):
            key = self._ordered_keys[self.cursor_row]
            return self._fingerprints.get(key)
        return None


def _format_risk(level: str) -> str:
    """Format risk level with markup."""
    styles = {
        "critical": "[bold reverse red] CRITICAL [/]",
        "high": "[bold red]HIGH[/]",
        "medium": "[yellow]MEDIUM[/]",
        "low": "[green]LOW[/]",
        "unknown": "[dim]UNKNOWN[/]",
    }
    return styles.get(level, level.upper())


def _format_ducky(fp: DeviceFingerprint) -> str:
    """Format ducky detection status."""
    if not fp.ducky.is_ducky:
        return "[green]No[/]"
    conf = fp.ducky.confidence
    if conf == "confirmed":
        label = fp.ducky.device_label or "BadUSB"
        return f"[bold reverse red] {label} [/]"
    if conf == "high":
        return "[bold red]PROBABLE[/]"
    return "[yellow]SUSPECT[/]"
