"""Program blocking via Software Restriction Policies (Windows only)."""

from __future__ import annotations

import logging
import platform

from dlp.audit.rollback import RollbackJournal
from dlp.platform.base import BlockRule, ProgramBlockerBase

logger = logging.getLogger(__name__)


class ProgramBlockController:
    """Orchestrates program blocking with rollback."""

    def __init__(
        self,
        blocker: ProgramBlockerBase | None,
        rollback: RollbackJournal,
    ) -> None:
        self.blocker = blocker
        self.rollback = rollback

    @property
    def available(self) -> bool:
        """Whether program blocking is available on this platform."""
        if self.blocker is None:
            return False
        return self.blocker.is_available()

    @property
    def unavailable_reason(self) -> str:
        """Reason why program blocking is unavailable."""
        if platform.system() != "Windows":
            return "Program blocking via Group Policy is only available on Windows."
        if self.blocker is None:
            return "Program blocker could not be initialized."
        if not self.blocker.is_available():
            return "Software Restriction Policies are not available on this Windows edition."
        return ""

    def block_program(self, path_pattern: str, description: str = "") -> str:
        """Block a program path. Returns status message."""
        if not self.available:
            return self.unavailable_reason

        assert self.blocker is not None
        rule_id = self.blocker.block_path(path_pattern, description)

        self.rollback.push(
            description=f"Block program: {path_pattern}",
            undo_fn=lambda: self.blocker.unblock_path(rule_id),  # type: ignore[union-attr]
            feature="program_block",
        )

        logger.info("Blocked program path: %s (rule: %s)", path_pattern, rule_id)
        return f"Blocked: {path_pattern} (rule ID: {rule_id})"

    def unblock_program(self, rule_id: str) -> str:
        """Remove a block rule. Returns status message."""
        if not self.available:
            return self.unavailable_reason

        assert self.blocker is not None
        self.blocker.unblock_path(rule_id)
        logger.info("Removed block rule: %s", rule_id)
        return f"Removed block rule: {rule_id}"

    def list_blocked(self) -> list[BlockRule]:
        """List all active block rules."""
        if not self.available:
            return []
        assert self.blocker is not None
        return self.blocker.list_rules()
