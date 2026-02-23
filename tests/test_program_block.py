"""Tests for program blocking (SRP) logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from dlp.audit.rollback import RollbackJournal
from dlp.features.program_block import ProgramBlockController
from dlp.platform.base import BlockRule


class FakeProgramBlocker:
    """In-memory fake for ProgramBlockerBase."""

    def __init__(self):
        self.rules: dict[str, BlockRule] = {}
        self._counter = 0
        self.dry_run = False

    def block_path(self, path_pattern: str, description: str = "") -> str:
        self._counter += 1
        rule_id = f"rule-{self._counter}"
        self.rules[rule_id] = BlockRule(
            rule_id=rule_id, path_pattern=path_pattern, description=description
        )
        return rule_id

    def unblock_path(self, rule_id: str) -> None:
        self.rules.pop(rule_id, None)

    def list_rules(self) -> list[BlockRule]:
        return list(self.rules.values())

    def is_available(self) -> bool:
        return True


def test_block_program():
    blocker = FakeProgramBlocker()
    rollback = RollbackJournal()
    controller = ProgramBlockController(blocker=blocker, rollback=rollback)

    msg = controller.block_program("C:\\Users\\*\\Downloads\\*.exe", "Block downloads")
    assert "rule-1" in msg
    assert len(blocker.rules) == 1


def test_unblock_program():
    blocker = FakeProgramBlocker()
    rollback = RollbackJournal()
    controller = ProgramBlockController(blocker=blocker, rollback=rollback)

    controller.block_program("C:\\Temp\\*.exe")
    assert len(blocker.rules) == 1

    controller.unblock_program("rule-1")
    assert len(blocker.rules) == 0


def test_list_blocked():
    blocker = FakeProgramBlocker()
    rollback = RollbackJournal()
    controller = ProgramBlockController(blocker=blocker, rollback=rollback)

    controller.block_program("C:\\path1\\*.exe")
    controller.block_program("C:\\path2\\*.bat")

    rules = controller.list_blocked()
    assert len(rules) == 2


def test_rollback_removes_rule():
    blocker = FakeProgramBlocker()
    rollback = RollbackJournal()
    controller = ProgramBlockController(blocker=blocker, rollback=rollback)

    controller.block_program("C:\\Temp\\*.exe")
    assert len(blocker.rules) == 1

    # Undo should remove the rule
    rollback.undo_last()
    assert len(blocker.rules) == 0


def test_unavailable_on_non_windows():
    controller = ProgramBlockController(blocker=None, rollback=RollbackJournal())
    assert controller.available is False
    msg = controller.block_program("test")
    assert "not available" in msg.lower() or "only available" in msg.lower()


def test_unavailable_returns_empty_rules():
    controller = ProgramBlockController(blocker=None, rollback=RollbackJournal())
    assert controller.list_blocked() == []


def test_windows_program_blocker_block_path():
    import sys

    mock_winreg = MagicMock()
    mock_winreg.HKEY_LOCAL_MACHINE = 0x80000002
    mock_winreg.KEY_WRITE = 0x20006
    mock_winreg.REG_SZ = 1
    mock_winreg.REG_DWORD = 4
    mock_key = MagicMock()
    mock_winreg.CreateKeyEx.return_value = mock_key

    old = sys.modules.get("winreg")
    sys.modules["winreg"] = mock_winreg
    try:
        from dlp.platform.windows import WindowsProgramBlocker

        blocker = WindowsProgramBlocker(dry_run=False)
        rule_id = blocker.block_path("C:\\Temp\\*.exe", "Test rule")

        assert rule_id  # Should return a UUID
        assert mock_winreg.SetValueEx.call_count >= 2  # ItemData + SaferFlags
    finally:
        if old is not None:
            sys.modules["winreg"] = old
        else:
            sys.modules.pop("winreg", None)


def test_windows_program_blocker_dry_run():
    from dlp.platform.windows import WindowsProgramBlocker

    blocker = WindowsProgramBlocker(dry_run=True)
    rule_id = blocker.block_path("C:\\Temp\\*.exe")
    assert rule_id  # Returns a UUID even in dry run
    # Should not raise (no winreg import)
    blocker.unblock_path(rule_id)
    assert blocker.list_rules() == []  # Dry run returns empty
