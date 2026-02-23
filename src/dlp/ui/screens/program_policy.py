"""Program blocking screen (Windows Group Policy / SRP)."""

from __future__ import annotations

import platform as _platform

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static

from dlp.platform.base import BlockRule


class ProgramPolicyScreen(Static):
    """Program execution restriction management."""

    def compose(self) -> ComposeResult:
        with Vertical(classes="feature-container"):
            yield Static(
                "Program Blocking (Group Policy / SRP)", classes="section-title"
            )
            yield Static("")

            if _platform.system() != "Windows":
                yield Static(
                    "This feature is only available on Windows.\n\n"
                    "On Windows, this screen allows you to create Software Restriction\n"
                    "Policies (SRP) that block program execution by path pattern.\n\n"
                    "Examples:\n"
                    "  - C:\\Users\\*\\Downloads\\*.exe  (block executables from Downloads)\n"
                    "  - C:\\Temp\\*                    (block anything from Temp)\n"
                    "  - %USERPROFILE%\\Desktop\\*.bat  (block batch files from Desktop)",
                    classes="unavailable-message",
                )
                return

            yield Static("", id="program-availability")

            # Add rule form
            yield Static("Add Block Rule", classes="section-title")
            with Horizontal(classes="whitelist-form"):
                yield Input(
                    placeholder="Path pattern (e.g. C:\\Users\\*\\Downloads\\*.exe)",
                    id="input-block-path",
                )
                yield Input(
                    placeholder="Description (optional)",
                    id="input-block-desc",
                )
                yield Button("Block Path", variant="error", id="btn-block-program")

            yield Static("")
            yield Static("Active Rules", classes="section-title")
            yield Static("", id="program-rules-list")

            # Rule removal
            with Horizontal(classes="whitelist-form"):
                yield Input(
                    placeholder="Rule ID prefix to remove",
                    id="input-remove-rule-id",
                )
                yield Button("Remove Rule", variant="error", id="btn-remove-rule")

            yield Static("")
            yield Static("Action Log", classes="section-title")
            yield Static("", id="program-action-log")

    def update_availability(self, available: bool, reason: str = "") -> None:
        try:
            widget = self.query_one("#program-availability", Static)
        except Exception:
            return
        if available:
            widget.update("[green]SRP is available on this system.[/]")
        else:
            widget.update(f"[red]{reason}[/]")

    def update_rules_list(self, rules: list[BlockRule]) -> None:
        try:
            widget = self.query_one("#program-rules-list", Static)
        except Exception:
            return
        if not rules:
            widget.update("[dim]No active block rules.[/]")
            return
        lines = []
        for r in rules:
            desc = f" ({r.description})" if r.description else ""
            lines.append(f"  [{r.rule_id[:8]}] {r.path_pattern}{desc}")
        widget.update("\n".join(lines))

    def append_log(self, message: str) -> None:
        try:
            widget = self.query_one("#program-action-log", Static)
        except Exception:
            return
        current = str(widget.content) if widget.content else ""
        lines = current.split("\n") if current else []
        lines.append(message)
        widget.update("\n".join(lines[-20:]))
