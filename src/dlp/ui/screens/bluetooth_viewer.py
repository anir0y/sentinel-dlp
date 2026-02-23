"""Bluetooth device viewer screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static

from dlp.features.bluetooth_monitor import BluetoothDeviceInfo


class BluetoothViewerScreen(Static):
    """Bluetooth device scanning and display."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="feature-container"):
            yield Static("Bluetooth Devices", classes="section-title")
            with Horizontal(classes="action-bar"):
                yield Button("Scan Bluetooth", variant="primary", id="btn-scan-bluetooth")
            yield Static("[dim]No scan performed yet.[/]", id="bt-status")
            yield DataTable(id="bt-table")

    def on_mount(self) -> None:
        table = self.query_one("#bt-table", DataTable)
        table.add_columns("Name", "Address", "Type", "Connected")

    def load_devices(self, devices: list[BluetoothDeviceInfo]) -> None:
        """Clear and populate the table with discovered Bluetooth devices."""
        table = self.query_one("#bt-table", DataTable)
        table.clear()
        for device in devices:
            connected = "[green]Yes[/]" if device.connected else "[red]No[/]"
            table.add_row(
                device.name,
                device.address,
                device.device_type,
                connected,
            )

    def update_scan_status(self, message: str) -> None:
        self.query_one("#bt-status", Static).update(message)
