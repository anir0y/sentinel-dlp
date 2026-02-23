"""Status bar widget showing privilege level and dry-run status."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static


class StatusBar(Static):
    """Persistent status bar at the top of the app."""

    def __init__(
        self,
        is_admin: bool = False,
        dry_run: bool = False,
        platform_name: str = "",
    ) -> None:
        super().__init__(id="status-bar")
        self._is_admin = is_admin
        self._dry_run = dry_run
        self._platform_name = platform_name

    def on_mount(self) -> None:
        self._refresh_display()

    def _refresh_display(self) -> None:
        parts: list[str] = []

        parts.append(f"Platform: {self._platform_name}")

        if self._dry_run:
            parts.append("[bold yellow][DRY RUN][/]")

        if self._is_admin:
            parts.append("[green]Admin[/]")
        else:
            parts.append("[red]No Admin Privileges[/]")

        self.update(" | ".join(parts))

    def set_dry_run(self, dry_run: bool) -> None:
        self._dry_run = dry_run
        self._refresh_display()
