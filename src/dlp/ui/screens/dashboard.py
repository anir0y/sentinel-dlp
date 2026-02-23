"""Dashboard screen showing DLP status overview."""

from __future__ import annotations

import platform as _platform

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static


class DashboardScreen(Static):
    """Main dashboard with status cards."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("DLP Control Panel", classes="section-title")
            yield Static("")
            with Horizontal():
                with Vertical(classes="dashboard-card"):
                    yield Static("USB Storage", classes="card-title")
                    yield Static("Status: checking...", id="usb-status", classes="card-value")
                with Vertical(classes="dashboard-card"):
                    yield Static("USB Whitelist", classes="card-title")
                    yield Static("Status: checking...", id="whitelist-status", classes="card-value")
            with Horizontal():
                with Vertical(classes="dashboard-card"):
                    yield Static("HID Devices", classes="card-title")
                    yield Static("Devices: scanning...", id="hid-status", classes="card-value")
                with Vertical(classes="dashboard-card"):
                    yield Static("Program Policy", classes="card-title")
                    yield Static("Status: checking...", id="program-status", classes="card-value")
            with Vertical(classes="dashboard-card"):
                yield Static("System Info", classes="card-title")
                yield Static(
                    f"OS: {_platform.system()} {_platform.release()}\n"
                    f"Python: {_platform.python_version()}\n"
                    f"Machine: {_platform.machine()}",
                    classes="card-value",
                )
            yield Static("")
            with Horizontal(classes="action-bar"):
                yield Button("Save Config", variant="primary", id="btn-save-config")
                yield Button("Export Policy", variant="default", id="btn-export-policy")
                yield Input(placeholder="Policy file path", id="input-policy-path")
                yield Button("Import Policy", variant="warning", id="btn-import-policy")

    def update_usb_status(self, blocked: bool, dry_run: bool) -> None:
        widget = self.query_one("#usb-status", Static)
        if dry_run:
            widget.update("Status: [yellow]DRY RUN[/] (simulated)")
        elif blocked:
            widget.update("Status: [bold red]BLOCKED[/]")
        else:
            widget.update("Status: [green]Enabled[/]")

    def update_whitelist_status(self, enabled: bool, count: int) -> None:
        widget = self.query_one("#whitelist-status", Static)
        if enabled:
            widget.update(f"Status: [green]Active[/] ({count} entries)")
        else:
            widget.update("Status: [dim]Disabled[/]")

    def update_hid_count(self, count: int) -> None:
        widget = self.query_one("#hid-status", Static)
        widget.update(f"Devices: {count} detected")

    def update_program_status(self, available: bool, rule_count: int = 0) -> None:
        widget = self.query_one("#program-status", Static)
        if not available:
            widget.update("Status: [dim]Not available (Windows only)[/]")
        elif rule_count > 0:
            widget.update(f"Status: [yellow]{rule_count} rules active[/]")
        else:
            widget.update("Status: [green]No restrictions[/]")
