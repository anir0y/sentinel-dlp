"""USB Manager screen for blocking/unblocking and whitelist management."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static


class USBManagerScreen(Static):
    """USB block/unblock controls and whitelist editor."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="feature-container"):
            yield Static("USB Storage Control", classes="section-title")
            yield Static("")

            # Block/Unblock section
            yield Static("Mass Storage Policy", classes="section-title")
            yield Static("Current: checking...", id="usb-block-status")
            with Horizontal(classes="action-bar"):
                yield Button("Block All USB Storage", variant="error", id="btn-block-usb")
                yield Button("Unblock USB Storage", variant="success", id="btn-unblock-usb")
                yield Button("Enforce Whitelist", variant="warning", id="btn-enforce-whitelist")

            yield Static("")
            yield Static("Whitelist Management", classes="section-title")
            yield Static("Add a device to the whitelist by VID/PID:", id="whitelist-hint")

            # Whitelist add form
            with Horizontal(classes="whitelist-form"):
                yield Input(placeholder="Vendor ID (e.g. 0781)", id="input-vid")
                yield Input(placeholder="Product ID (e.g. 5583)", id="input-pid")
                yield Input(placeholder="Serial (optional)", id="input-serial")
                yield Input(placeholder="Label (optional)", id="input-label")
                yield Button("Add", variant="primary", id="btn-add-whitelist")

            # Whitelist entry removal
            with Horizontal(classes="whitelist-form"):
                yield Input(placeholder="Entry # to remove", id="input-remove-whitelist-idx")
                yield Button("Remove", variant="error", id="btn-remove-whitelist")

            # Whitelist entries display
            yield Static("", id="whitelist-entries")

            # Action log
            yield Static("")
            yield Static("Action Log", classes="section-title")
            yield Static("", id="usb-action-log")

    def update_block_status(self, blocked: bool, dry_run: bool) -> None:
        widget = self.query_one("#usb-block-status", Static)
        if dry_run:
            widget.update("Current: [yellow]DRY RUN MODE[/] (no real changes)")
        elif blocked:
            widget.update("Current: [bold red]USB Mass Storage BLOCKED[/]")
        else:
            widget.update("Current: [green]USB Mass Storage Enabled[/]")

    def update_whitelist_display(self, entries: list[dict]) -> None:
        widget = self.query_one("#whitelist-entries", Static)
        if not entries:
            widget.update("[dim]No whitelist entries.[/]")
            return
        lines = []
        for i, e in enumerate(entries, 1):
            serial = e.get("serial_number") or "-"
            label = e.get("label") or ""
            lines.append(
                f"  {i}. VID:{e['vendor_id']} PID:{e['product_id']} "
                f"Serial:{serial} {label}"
            )
        widget.update("\n".join(lines))

    def append_log(self, message: str) -> None:
        widget = self.query_one("#usb-action-log", Static)
        current = str(widget.content) if widget.content else ""
        # Keep last 20 lines
        lines = current.split("\n") if current else []
        lines.append(message)
        widget.update("\n".join(lines[-20:]))
