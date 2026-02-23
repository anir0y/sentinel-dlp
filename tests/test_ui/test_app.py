"""TUI integration tests using Textual's pilot."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dlp.app import DLPApp


@pytest.fixture
def mock_platform():
    """Mock platform detection to avoid actual OS calls."""
    with (
        patch("dlp.app.is_admin", return_value=False),
        patch("dlp.app.get_platform_name", return_value="macOS 14.0 (Test)"),
        patch("dlp.app.get_usb_manager") as mock_usb,
        patch("dlp.app.get_program_blocker", return_value=None),
    ):
        # Create a mock USB manager
        manager = MagicMock()
        manager.dry_run = True
        manager.is_mass_storage_blocked.return_value = False
        manager.enumerate_devices.return_value = []
        manager.enumerate_hid_devices.return_value = []
        manager.get_blocked_devices.return_value = []
        mock_usb.return_value = manager
        yield manager


@pytest.mark.asyncio
async def test_app_starts_and_shows_title(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        assert app.title == "DLP Control Panel"


@pytest.mark.asyncio
async def test_app_has_eight_tabs(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        tabs = app.query("TabPane")
        assert len(tabs) == 8


@pytest.mark.asyncio
async def test_app_dry_run_flag(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        assert app.dry_run is True


@pytest.mark.asyncio
async def test_app_quit_binding(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("q")
        # App should attempt to quit (may or may not be running)
