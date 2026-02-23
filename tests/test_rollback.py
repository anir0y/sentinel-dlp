"""Tests for the rollback journal."""

from __future__ import annotations

import pytest

from dlp.audit.rollback import RollbackJournal


def test_push_and_undo(rollback_journal):
    called = []
    rollback_journal.push("Block USB", lambda: called.append("unblocked"), "usb_block")
    assert rollback_journal.size == 1

    desc = rollback_journal.undo_last()
    assert desc == "Block USB"
    assert called == ["unblocked"]
    assert rollback_journal.size == 0


def test_undo_empty_returns_none(rollback_journal):
    assert rollback_journal.undo_last() is None


def test_lifo_order(rollback_journal):
    order = []
    rollback_journal.push("First", lambda: order.append(1), "test")
    rollback_journal.push("Second", lambda: order.append(2), "test")
    rollback_journal.push("Third", lambda: order.append(3), "test")

    rollback_journal.undo_last()
    rollback_journal.undo_last()
    rollback_journal.undo_last()
    assert order == [3, 2, 1]


def test_max_entries():
    journal = RollbackJournal(max_entries=3)
    for i in range(5):
        journal.push(f"action-{i}", lambda: None, "test")
    assert journal.size == 3


def test_peek(rollback_journal):
    assert rollback_journal.peek() is None
    rollback_journal.push("Test", lambda: None, "test")
    entry = rollback_journal.peek()
    assert entry is not None
    assert entry.description == "Test"
    # peek should not remove
    assert rollback_journal.size == 1


def test_list_entries(rollback_journal):
    rollback_journal.push("First", lambda: None, "test")
    rollback_journal.push("Second", lambda: None, "test")
    entries = rollback_journal.list_entries()
    # Most recent first
    assert entries[0].description == "Second"
    assert entries[1].description == "First"


def test_clear(rollback_journal):
    rollback_journal.push("Test", lambda: None, "test")
    rollback_journal.clear()
    assert rollback_journal.size == 0


def test_undo_propagates_exception(rollback_journal):
    def failing_undo():
        raise RuntimeError("Undo failed!")

    rollback_journal.push("Bad action", failing_undo, "test")
    with pytest.raises(RuntimeError, match="Undo failed"):
        rollback_journal.undo_last()


# ---------------------------------------------------------------------------
# undo_at_index tests
# ---------------------------------------------------------------------------


def test_undo_at_index_most_recent(rollback_journal):
    called = []
    rollback_journal.push("First", lambda: called.append(1), "test")
    rollback_journal.push("Second", lambda: called.append(2), "test")
    rollback_journal.push("Third", lambda: called.append(3), "test")

    desc = rollback_journal.undo_at_index(0)  # most recent = "Third"
    assert desc == "Third"
    assert called == [3]
    assert rollback_journal.size == 2


def test_undo_at_index_middle(rollback_journal):
    called = []
    rollback_journal.push("First", lambda: called.append(1), "test")
    rollback_journal.push("Second", lambda: called.append(2), "test")
    rollback_journal.push("Third", lambda: called.append(3), "test")

    desc = rollback_journal.undo_at_index(1)  # middle = "Second"
    assert desc == "Second"
    assert called == [2]
    assert rollback_journal.size == 2
    # Remaining should be First and Third
    entries = rollback_journal.list_entries()
    assert [e.description for e in entries] == ["Third", "First"]


def test_undo_at_index_oldest(rollback_journal):
    called = []
    rollback_journal.push("First", lambda: called.append(1), "test")
    rollback_journal.push("Second", lambda: called.append(2), "test")

    desc = rollback_journal.undo_at_index(1)  # oldest = "First"
    assert desc == "First"
    assert called == [1]
    assert rollback_journal.size == 1


def test_undo_at_index_invalid(rollback_journal):
    rollback_journal.push("Only", lambda: None, "test")
    assert rollback_journal.undo_at_index(-1) is None
    assert rollback_journal.undo_at_index(1) is None
    assert rollback_journal.undo_at_index(99) is None
    assert rollback_journal.size == 1  # nothing removed


def test_undo_at_index_empty(rollback_journal):
    assert rollback_journal.undo_at_index(0) is None
