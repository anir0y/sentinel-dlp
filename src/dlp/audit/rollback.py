"""Rollback journal for undoing destructive DLP actions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class RollbackEntry:
    """A single rollback entry with its undo function."""

    timestamp: datetime
    description: str
    undo_fn: Callable[[], None]
    feature: str  # "usb_block", "usb_whitelist", "program_block"


class RollbackJournal:
    """Stack-based undo journal. Every destructive action pushes its inverse."""

    def __init__(self, max_entries: int = 100) -> None:
        self._stack: list[RollbackEntry] = []
        self._max = max_entries

    def push(
        self, description: str, undo_fn: Callable[[], None], feature: str
    ) -> None:
        """Record an action and its inverse."""
        entry = RollbackEntry(
            timestamp=datetime.now(),
            description=description,
            undo_fn=undo_fn,
            feature=feature,
        )
        self._stack.append(entry)
        if len(self._stack) > self._max:
            self._stack.pop(0)
        logger.debug("Rollback entry pushed: %s", description)

    def undo_last(self) -> str | None:
        """Undo the most recent action. Returns description or None if empty."""
        if not self._stack:
            return None
        entry = self._stack.pop()
        try:
            entry.undo_fn()
            logger.info("Rolled back: %s", entry.description)
            return entry.description
        except Exception:
            logger.exception("Failed to rollback: %s", entry.description)
            raise

    def peek(self) -> RollbackEntry | None:
        """View the most recent entry without removing it."""
        return self._stack[-1] if self._stack else None

    def list_entries(self) -> list[RollbackEntry]:
        """Return all entries, most recent first."""
        return list(reversed(self._stack))

    @property
    def size(self) -> int:
        return len(self._stack)

    def undo_at_index(self, index: int) -> str | None:
        """Undo a specific entry by index (0 = most recent).

        The entry is removed from the stack and its undo function called.
        Returns description or None if index is invalid.
        """
        entries = self.list_entries()  # most recent first
        if index < 0 or index >= len(entries):
            return None
        entry = entries[index]
        # Convert to internal stack index (oldest-first)
        stack_index = len(self._stack) - 1 - index
        self._stack.pop(stack_index)
        try:
            entry.undo_fn()
            logger.info("Rolled back (index %d): %s", index, entry.description)
            return entry.description
        except Exception:
            logger.exception("Failed to rollback (index %d): %s", index, entry.description)
            raise

    def clear(self) -> None:
        """Clear all entries without executing undo functions."""
        self._stack.clear()
