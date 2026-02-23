"""Network exfiltration monitoring screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static


class NetworkMonitorScreen(Static):
    """Network I/O monitoring display."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="feature-container"):
            yield Static("Network Exfiltration Monitor", classes="section-title")
            with Horizontal(classes="action-bar"):
                yield Button("Check Now", variant="primary", id="btn-check-network")
            yield Static("[dim]Network monitoring disabled. Enable in config.[/]", id="net-status")
            yield Static("", id="net-alerts")

    def update_status(self, status: str) -> None:
        self.query_one("#net-status", Static).update(status)

    def append_alert(self, message: str) -> None:
        widget = self.query_one("#net-alerts", Static)
        current = str(widget.content) if widget.content else ""
        lines = current.split("\n") if current else []
        lines.append(message)
        widget.update("\n".join(lines[-30:]))
