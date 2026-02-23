"""Audit log viewer screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static


class AuditViewerScreen(Static):
    """Audit log viewing and filtering display."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="feature-container"):
            yield Static("Audit Log Viewer", classes="section-title")
            with Horizontal(classes="action-bar"):
                yield Button("Refresh", variant="primary", id="btn-refresh-audit")
                yield Input(placeholder="Filter by feature", id="input-audit-filter")
            yield DataTable(id="audit-table")

    def on_mount(self) -> None:
        table = self.query_one("#audit-table", DataTable)
        table.add_columns("Timestamp", "Feature", "Action", "Success", "Dry Run", "Details")

    def load_entries(self, entries: list[dict], filter_feature: str = "") -> None:
        """Clear and populate the audit table with log entries.

        Entries are shown most-recent first. Details are truncated to 50 chars.
        If filter_feature is provided, only matching entries are shown.
        """
        table = self.query_one("#audit-table", DataTable)
        table.clear()

        filtered = entries
        if filter_feature:
            filtered = [
                e for e in entries
                if filter_feature.lower() in e.get("feature", "").lower()
            ]

        for entry in reversed(filtered):
            timestamp = entry.get("timestamp", "")
            feature = entry.get("feature", "")
            action = entry.get("action", "")
            success = entry.get("success", False)
            dry_run = entry.get("dry_run", False)
            details = entry.get("details", "")

            success_display = "[green]Yes[/]" if success else "[red]No[/]"
            dry_run_display = "Yes" if dry_run else "No"
            details_truncated = details[:50] + "..." if len(details) > 50 else details

            table.add_row(
                str(timestamp),
                feature,
                action,
                success_display,
                dry_run_display,
                details_truncated,
            )
