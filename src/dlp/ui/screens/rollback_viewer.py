"""Rollback history viewer screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Static

from dlp.audit.rollback import RollbackEntry


class RollbackViewerScreen(Static):
    """Rollback history viewing and undo display."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="feature-container"):
            yield Static("Rollback History", classes="section-title")
            with Horizontal(classes="action-bar"):
                yield Button("Refresh", variant="primary", id="btn-refresh-rollback")
                yield Input(placeholder="Entry # to undo", id="input-undo-index")
                yield Button("Undo Selected", variant="error", id="btn-undo-selected")
            yield DataTable(id="rollback-table")

    def on_mount(self) -> None:
        table = self.query_one("#rollback-table", DataTable)
        table.add_columns("#", "Timestamp", "Feature", "Description")

    def load_entries(self, entries: list[RollbackEntry]) -> None:
        """Populate the rollback table with RollbackEntry objects.

        Entries are displayed with 1-indexed row numbers and formatted timestamps.
        """
        table = self.query_one("#rollback-table", DataTable)
        table.clear()
        for index, entry in enumerate(entries, start=1):
            timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            table.add_row(
                str(index),
                timestamp,
                entry.feature,
                entry.description,
            )
