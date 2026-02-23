"""Screen-level integration tests using Textual's pilot."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dlp.app import DLPApp
from dlp.config import DLPConfig, WhitelistEntry
from dlp.platform.base import USBDeviceInfo
from dlp.ui.widgets.confirm_modal import ConfirmModal


@pytest.fixture
def mock_platform():
    """Mock platform detection to avoid actual OS calls."""
    with (
        patch("dlp.app.is_admin", return_value=False),
        patch("dlp.app.get_platform_name", return_value="macOS 14.0 (Test)"),
        patch("dlp.app.get_usb_manager") as mock_usb,
        patch("dlp.app.get_program_blocker", return_value=None),
    ):
        manager = MagicMock()
        manager.dry_run = True
        manager.is_mass_storage_blocked.return_value = False
        manager.enumerate_devices.return_value = []
        manager.enumerate_hid_devices.return_value = []
        manager.get_blocked_devices.return_value = []
        mock_usb.return_value = manager
        yield manager


# ---------------------------------------------------------------------------
# Tab switching tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_switch_to_usb_tab(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("u")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-usb"


@pytest.mark.asyncio
async def test_switch_to_hid_tab(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("h")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-hid"


@pytest.mark.asyncio
async def test_switch_to_programs_tab(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("p")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-programs"


@pytest.mark.asyncio
async def test_switch_to_network_tab(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("n")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-network"


@pytest.mark.asyncio
async def test_switch_to_bluetooth_tab(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("b")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-bluetooth"


@pytest.mark.asyncio
async def test_switch_to_audit_tab(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("a")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-audit"


@pytest.mark.asyncio
async def test_switch_to_rollback_tab(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("o")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-rollback"


@pytest.mark.asyncio
async def test_switch_back_to_dashboard(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("u")
        await pilot.press("d")
        tabs = app.query_one("TabbedContent")
        assert tabs.active == "tab-dashboard"


# ---------------------------------------------------------------------------
# Dashboard screen tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_shows_dry_run(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        from dlp.ui.screens.dashboard import DashboardScreen
        from textual.widgets import Static

        dashboard = app.query_one("#dashboard", DashboardScreen)
        usb_status = dashboard.query_one("#usb-status", Static)
        assert "DRY RUN" in str(usb_status.content)


@pytest.mark.asyncio
async def test_dashboard_save_button_exists(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        btn = app.query_one("#btn-save-config")
        assert btn is not None


@pytest.mark.asyncio
async def test_dashboard_export_import_buttons_exist(mock_platform):
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        assert app.query_one("#btn-export-policy") is not None
        assert app.query_one("#btn-import-policy") is not None
        assert app.query_one("#input-policy-path") is not None


# ---------------------------------------------------------------------------
# USB Manager screen tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usb_block_flow_shows_modal(mock_platform):
    """Calling block handler should push a ConfirmModal onto the screen stack."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        app._handle_block_usb()
        await pilot.pause()
        assert len(app.screen_stack) == 2
        assert isinstance(app.screen, ConfirmModal)


@pytest.mark.asyncio
async def test_usb_block_confirm_blocks(mock_platform):
    """Confirming the modal should complete without error."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        app._handle_block_usb()
        await pilot.pause()
        # Click confirm button on the modal
        confirm_btn = app.screen.query_one("#confirm-yes")
        confirm_btn.press()
        await pilot.pause()
        # Modal should be dismissed
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_usb_block_cancel_does_nothing(mock_platform):
    """Cancelling the modal should dismiss without blocking."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        app._handle_block_usb()
        await pilot.pause()
        cancel_btn = app.screen.query_one("#confirm-no")
        cancel_btn.press()
        await pilot.pause()
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_usb_unblock(mock_platform):
    """Unblock handler should work without modal."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        app._handle_unblock_usb()
        await pilot.pause()
        # Should not crash, no modal for unblock


@pytest.mark.asyncio
async def test_add_whitelist_requires_vid_pid(mock_platform):
    """Adding a whitelist entry without VID/PID should not add anything."""
    config = DLPConfig()  # clean config, no whitelist entries
    app = DLPApp(dry_run=True, config=config)
    async with app.run_test() as pilot:
        app._handle_add_whitelist()
        await pilot.pause()
        assert len(app.config.usb.whitelist) == 0


@pytest.mark.asyncio
async def test_add_whitelist_entry(mock_platform):
    """Adding a whitelist entry with VID/PID should succeed."""
    config = DLPConfig()  # clean config, no whitelist entries
    app = DLPApp(dry_run=True, config=config)
    async with app.run_test() as pilot:
        from textual.widgets import Input

        vid_input = app.query_one("#input-vid", Input)
        pid_input = app.query_one("#input-pid", Input)
        label_input = app.query_one("#input-label", Input)

        vid_input.value = "0781"
        pid_input.value = "5583"
        label_input.value = "Test USB"

        app._handle_add_whitelist()
        await pilot.pause()

        assert len(app.config.usb.whitelist) >= 1
        entry = app.config.usb.whitelist[-1]  # last added
        assert entry.vendor_id == "0781"
        assert entry.product_id == "5583"
        assert entry.label == "Test USB"
        assert vid_input.value == ""


@pytest.mark.asyncio
async def test_remove_whitelist_entry(mock_platform):
    """Removing a whitelist entry by index."""
    config = DLPConfig(
        usb={
            "whitelist_enabled": True,
            "whitelist": [
                WhitelistEntry(vendor_id="0781", product_id="5583", label="Drive A"),
                WhitelistEntry(vendor_id="0951", product_id="1666", label="Drive B"),
            ],
        }
    )
    app = DLPApp(dry_run=True, config=config)
    async with app.run_test() as pilot:
        from textual.widgets import Input

        idx_input = app.query_one("#input-remove-whitelist-idx", Input)
        idx_input.value = "1"  # remove first entry (1-based)

        app._handle_remove_whitelist()
        await pilot.pause()

        assert len(app.config.usb.whitelist) == 1
        assert app.config.usb.whitelist[0].label == "Drive B"


# ---------------------------------------------------------------------------
# HID Viewer screen tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_hid_populates_table(mock_platform):
    """Scan Devices handler should populate the HID table with mock devices."""
    hid_device = USBDeviceInfo(
        vendor_id="046d",
        product_id="c52b",
        serial_number="",
        manufacturer="Logitech",
        product_name="Unifying Receiver",
        device_class="hid",
        device_path="USB\\VID_046D&PID_C52B\\0000",
    )
    mock_platform.enumerate_hid_devices.return_value = [hid_device]

    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        # Switch to HID tab to ensure DeviceTable is mounted with columns
        await pilot.press("h")
        await pilot.pause()

        app._handle_scan_hid()
        await pilot.pause()

        from dlp.ui.widgets.device_table import DeviceTable

        table = app.query_one("#hid-table", DeviceTable)
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_scan_all_usb_devices(mock_platform):
    """Scan All handler should populate with all USB devices."""
    devices = [
        USBDeviceInfo(
            vendor_id="0781",
            product_id="5583",
            serial_number="ABC123",
            manufacturer="SanDisk",
            product_name="Ultra",
            device_class="mass_storage",
            device_path="USB\\VID_0781&PID_5583\\ABC123",
        ),
        USBDeviceInfo(
            vendor_id="046d",
            product_id="c52b",
            serial_number="",
            manufacturer="Logitech",
            product_name="Unifying Receiver",
            device_class="hid",
            device_path="USB\\VID_046D&PID_C52B\\0000",
        ),
    ]
    mock_platform.enumerate_devices.return_value = devices

    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("h")
        await pilot.pause()

        app._handle_scan_all()
        await pilot.pause()

        from dlp.ui.widgets.device_table import DeviceTable

        table = app.query_one("#hid-table", DeviceTable)
        assert table.row_count == 2


# ---------------------------------------------------------------------------
# Undo keybinding test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_undo_keybinding(mock_platform):
    """Pressing z should undo the last rollback entry."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        called = []
        app.rollback.push("Test action", lambda: called.append(True), "test")
        assert app.rollback.size == 1

        await pilot.press("z")
        await pilot.pause()

        assert app.rollback.size == 0
        assert called == [True]


@pytest.mark.asyncio
async def test_undo_empty_rollback(mock_platform):
    """Pressing z with nothing to undo should just notify."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        assert app.rollback.size == 0
        await pilot.press("z")
        await pilot.pause()
        assert app.rollback.size == 0


# ---------------------------------------------------------------------------
# Refresh keybinding test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_keybinding(mock_platform):
    """Pressing r should refresh all status without error."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("r")
        await pilot.pause()


# ---------------------------------------------------------------------------
# Network Monitor screen tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_network_screen_check_button(mock_platform):
    """Check Now button exists on network tab."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("n")
        btn = app.query_one("#btn-check-network")
        assert btn is not None


@pytest.mark.asyncio
async def test_network_screen_manual_check(mock_platform):
    """Manual network check handler should run without error."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        app._handle_check_network()
        await pilot.pause()
        # Should not crash even without psutil


# ---------------------------------------------------------------------------
# Bluetooth Viewer screen tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bluetooth_screen_scan_button(mock_platform):
    """Scan Bluetooth button exists on bluetooth tab."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("b")
        btn = app.query_one("#btn-scan-bluetooth")
        assert btn is not None


@pytest.mark.asyncio
async def test_bluetooth_screen_scan_populates(mock_platform):
    """Scanning bluetooth should populate the table with devices."""
    from dlp.features.bluetooth_monitor import BluetoothDeviceInfo

    mock_devices = [
        BluetoothDeviceInfo(
            name="AirPods Pro",
            address="AA:BB:CC:DD:EE:FF",
            device_type="audio",
            connected=True,
        ),
        BluetoothDeviceInfo(
            name="Magic Mouse",
            address="11:22:33:44:55:66",
            device_type="input",
            connected=False,
        ),
    ]

    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        with patch(
            "dlp.features.bluetooth_monitor.enumerate_bluetooth_devices",
            return_value=mock_devices,
        ):
            app._handle_scan_bluetooth()
            await pilot.pause()

        from textual.widgets import DataTable

        table = app.query_one("#bt-table", DataTable)
        assert table.row_count == 2


# ---------------------------------------------------------------------------
# Audit Viewer screen tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_screen_refresh_button(mock_platform):
    """Refresh button exists on audit tab."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("a")
        btn = app.query_one("#btn-refresh-audit")
        assert btn is not None


@pytest.mark.asyncio
async def test_audit_screen_refresh_loads_entries(mock_platform):
    """Refreshing audit log should load entries without error."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        with patch("dlp.app.read_recent_entries", return_value=[]):
            app._handle_refresh_audit()
            await pilot.pause()


@pytest.mark.asyncio
async def test_audit_screen_filter_input(mock_platform):
    """Filter input exists on audit tab."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        await pilot.press("a")
        from textual.widgets import Input

        filter_input = app.query_one("#input-audit-filter", Input)
        assert filter_input is not None


# ---------------------------------------------------------------------------
# Rollback Viewer screen tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollback_screen_refresh(mock_platform):
    """Refresh handler populates the rollback table."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        app.rollback.push("Action 1", lambda: None, "test")
        app.rollback.push("Action 2", lambda: None, "test")

        app._handle_refresh_rollback()
        await pilot.pause()

        from textual.widgets import DataTable

        table = app.query_one("#rollback-table", DataTable)
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_rollback_screen_undo_selected(mock_platform):
    """Undoing a selected rollback entry by index."""
    called = []
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        app.rollback.push("Action 1", lambda: called.append(1), "test")
        app.rollback.push("Action 2", lambda: called.append(2), "test")

        from textual.widgets import Input

        idx_input = app.query_one("#input-undo-index", Input)
        idx_input.value = "1"  # Undo the most recent (1-based)

        app._handle_undo_selected()
        await pilot.pause()

        assert 2 in called  # Most recent entry (index 0 in 0-based) was "Action 2"
        assert app.rollback.size == 1


# ---------------------------------------------------------------------------
# Hotplug detection test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hotplug_detects_new_device(mock_platform):
    """Hotplug polling should detect added devices."""
    device_a = USBDeviceInfo(
        vendor_id="0781",
        product_id="5583",
        serial_number="ABC",
        manufacturer="SanDisk",
        product_name="Ultra",
        device_class="mass_storage",
        device_path="USB\\VID_0781",
    )
    device_b = USBDeviceInfo(
        vendor_id="046d",
        product_id="c52b",
        serial_number="",
        manufacturer="Logitech",
        product_name="Receiver",
        device_class="hid",
        device_path="USB\\VID_046D",
    )

    # Use a config with very long poll interval to prevent timer interference
    config = DLPConfig(monitoring={"hotplug_poll_interval_seconds": 9999.0})
    mock_platform.enumerate_devices.return_value = [device_a]
    app = DLPApp(dry_run=True, config=config)
    async with app.run_test() as pilot:
        # Prime: first call with empty _last_device_paths sets the initial state
        app._last_device_paths = set()
        app._check_hotplug()
        assert app._last_device_paths == {"USB\\VID_0781"}

        # Second poll: two devices → detects addition
        mock_platform.enumerate_devices.return_value = [device_a, device_b]
        app._check_hotplug()
        assert app._last_device_paths == {"USB\\VID_0781", "USB\\VID_046D"}


@pytest.mark.asyncio
async def test_hotplug_detects_removed_device(mock_platform):
    """Hotplug should detect removed devices."""
    device_a = USBDeviceInfo(
        vendor_id="0781",
        product_id="5583",
        serial_number="ABC",
        manufacturer="SanDisk",
        product_name="Ultra",
        device_class="mass_storage",
        device_path="USB\\VID_0781",
    )

    config = DLPConfig(monitoring={"hotplug_poll_interval_seconds": 9999.0})
    mock_platform.enumerate_devices.return_value = [device_a]
    app = DLPApp(dry_run=True, config=config)
    async with app.run_test() as pilot:
        app._last_device_paths = set()
        app._check_hotplug()
        assert "USB\\VID_0781" in app._last_device_paths

        # Remove the device
        mock_platform.enumerate_devices.return_value = []
        app._check_hotplug()
        assert app._last_device_paths == set()


# ---------------------------------------------------------------------------
# Config save test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_config_handler(mock_platform):
    """Save Config handler should attempt to save without error."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        with patch("dlp.config.DLPConfig.to_toml") as mock_save:
            app._handle_save_config()
            await pilot.pause()
            mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_export_policy_handler(mock_platform):
    """Export policy handler should write JSON file."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        from textual.widgets import Input

        path_input = app.query_one("#input-policy-path", Input)
        path_input.value = "/tmp/test_dlp_export.json"

        with patch("dlp.features.policy_export.export_policy") as mock_export:
            app._handle_export_policy()
            await pilot.pause()
            mock_export.assert_called_once()


@pytest.mark.asyncio
async def test_import_policy_handler(mock_platform):
    """Import policy handler should load config from JSON."""
    app = DLPApp(dry_run=True)
    async with app.run_test() as pilot:
        from textual.widgets import Input

        path_input = app.query_one("#input-policy-path", Input)
        path_input.value = "/tmp/test_dlp_import.json"

        new_config = DLPConfig()
        with patch(
            "dlp.features.policy_export.import_policy", return_value=new_config
        ):
            app._handle_import_policy()
            await pilot.pause()
            assert app.config is new_config
