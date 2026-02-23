"""Widget unit tests using Textual's pilot."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dlp.features.hid_fingerprint import DeviceFingerprint, DuckyMatch
from dlp.platform.base import USBDeviceInfo
from dlp.ui.widgets.confirm_modal import ConfirmModal
from dlp.ui.widgets.device_table import DeviceTable, _format_ducky, _format_risk
from dlp.ui.widgets.status_bar import StatusBar


# ---------------------------------------------------------------------------
# DeviceTable tests
# ---------------------------------------------------------------------------


def _make_fingerprint(
    vendor_id: str = "046d",
    product_id: str = "c52b",
    product_name: str = "Unifying Receiver",
    device_class: str = "hid",
    device_path: str = "USB\\VID_046D&PID_C52B\\0000",
    is_ducky: bool = False,
    risk_level: str = "low",
) -> DeviceFingerprint:
    """Helper to create a DeviceFingerprint with minimal boilerplate."""
    device = USBDeviceInfo(
        vendor_id=vendor_id,
        product_id=product_id,
        serial_number="",
        manufacturer="Test Mfg",
        product_name=product_name,
        device_class=device_class,
        device_path=device_path,
    )
    ducky = DuckyMatch(
        is_ducky=is_ducky,
        confidence="confirmed" if is_ducky else "none",
        reason="test",
        device_label="BadUSB" if is_ducky else "",
    )
    return DeviceFingerprint(
        device=device,
        vendor_name="Test Vendor",
        is_known_vendor=True,
        risk_level=risk_level,
        risk_reason="test reason",
        ducky=ducky,
    )


class TestDeviceTableGetSelectedFingerprint:
    """Tests for DeviceTable.get_selected_fingerprint()."""

    @pytest.mark.asyncio
    async def test_no_selection_returns_none(self):
        """Before loading devices, get_selected_fingerprint returns None."""
        from textual.app import App, ComposeResult

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DeviceTable(id="test-table")

        app = TestApp()
        async with app.run_test() as pilot:
            table = app.query_one("#test-table", DeviceTable)
            assert table.get_selected_fingerprint() is None

    @pytest.mark.asyncio
    async def test_returns_correct_fingerprint(self):
        """After loading devices, get_selected_fingerprint returns the highlighted device."""
        from textual.app import App, ComposeResult

        fps = [
            _make_fingerprint(
                vendor_id="0781",
                product_name="SanDisk",
                device_path="USB\\VID_0781",
            ),
            _make_fingerprint(
                vendor_id="046d",
                product_name="Logitech",
                device_path="USB\\VID_046D",
            ),
        ]

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DeviceTable(id="test-table")

        app = TestApp()
        async with app.run_test() as pilot:
            table = app.query_one("#test-table", DeviceTable)
            table.load_devices(fps)
            await pilot.pause()

            # First row is selected by default (cursor_row=0)
            fp = table.get_selected_fingerprint()
            assert fp is not None
            assert fp.device.vendor_id == "0781"

    @pytest.mark.asyncio
    async def test_empty_table_returns_none(self):
        """Loading empty list then getting selection returns None."""
        from textual.app import App, ComposeResult

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield DeviceTable(id="test-table")

        app = TestApp()
        async with app.run_test() as pilot:
            table = app.query_one("#test-table", DeviceTable)
            table.load_devices([])
            await pilot.pause()
            assert table.get_selected_fingerprint() is None


# ---------------------------------------------------------------------------
# _format_risk tests
# ---------------------------------------------------------------------------


class TestFormatRisk:
    def test_critical(self):
        result = _format_risk("critical")
        assert "CRITICAL" in result

    def test_high(self):
        result = _format_risk("high")
        assert "HIGH" in result

    def test_medium(self):
        result = _format_risk("medium")
        assert "MEDIUM" in result

    def test_low(self):
        result = _format_risk("low")
        assert "LOW" in result

    def test_unknown(self):
        result = _format_risk("unknown")
        assert "UNKNOWN" in result

    def test_fallback(self):
        result = _format_risk("custom_level")
        assert "CUSTOM_LEVEL" in result


# ---------------------------------------------------------------------------
# _format_ducky tests
# ---------------------------------------------------------------------------


class TestFormatDucky:
    def test_not_ducky(self):
        fp = _make_fingerprint(is_ducky=False)
        result = _format_ducky(fp)
        assert "No" in result

    def test_confirmed_ducky(self):
        fp = _make_fingerprint(is_ducky=True)
        # confirmed confidence → shows device_label "BadUSB"
        result = _format_ducky(fp)
        assert "BadUSB" in result

    def test_high_confidence_ducky(self):
        device = USBDeviceInfo(
            vendor_id="1234",
            product_id="5678",
            serial_number="",
            manufacturer="Test",
            product_name="Test",
            device_class="hid",
            device_path="USB\\TEST",
        )
        ducky = DuckyMatch(
            is_ducky=True,
            confidence="high",
            reason="suspicious",
            device_label="",
        )
        fp = DeviceFingerprint(
            device=device,
            vendor_name="Test",
            is_known_vendor=False,
            risk_level="high",
            risk_reason="unknown vendor",
            ducky=ducky,
        )
        result = _format_ducky(fp)
        assert "PROBABLE" in result

    def test_suspect_ducky(self):
        device = USBDeviceInfo(
            vendor_id="1234",
            product_id="5678",
            serial_number="",
            manufacturer="Test",
            product_name="Test",
            device_class="hid",
            device_path="USB\\TEST",
        )
        ducky = DuckyMatch(
            is_ducky=True,
            confidence="medium",
            reason="suspicious",
            device_label="",
        )
        fp = DeviceFingerprint(
            device=device,
            vendor_name="Test",
            is_known_vendor=False,
            risk_level="medium",
            risk_reason="unknown vendor",
            ducky=ducky,
        )
        result = _format_ducky(fp)
        assert "SUSPECT" in result


# ---------------------------------------------------------------------------
# ConfirmModal tests
# ---------------------------------------------------------------------------


class TestConfirmModal:
    @pytest.mark.asyncio
    async def test_confirm_returns_true(self):
        """Clicking Confirm should dismiss with True."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class TestApp(App):
            result = None

            def compose(self) -> ComposeResult:
                yield Static("Base")

            def on_mount(self) -> None:
                def callback(value: bool) -> None:
                    self.result = value

                self.push_screen(
                    ConfirmModal("Test", "Are you sure?"), callback
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#confirm-yes")
            await pilot.pause()
            assert app.result is True

    @pytest.mark.asyncio
    async def test_cancel_returns_false(self):
        """Clicking Cancel should dismiss with False."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class TestApp(App):
            result = None

            def compose(self) -> ComposeResult:
                yield Static("Base")

            def on_mount(self) -> None:
                def callback(value: bool) -> None:
                    self.result = value

                self.push_screen(
                    ConfirmModal("Test", "Are you sure?"), callback
                )

        app = TestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#confirm-no")
            await pilot.pause()
            assert app.result is False


# ---------------------------------------------------------------------------
# StatusBar tests
# ---------------------------------------------------------------------------


class TestStatusBar:
    @pytest.mark.asyncio
    async def test_shows_platform(self):
        from textual.app import App, ComposeResult

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield StatusBar(
                    is_admin=False, dry_run=False, platform_name="TestOS"
                )

        app = TestApp()
        async with app.run_test() as pilot:
            bar = app.query_one("#status-bar", StatusBar)
            rendered = str(bar.content)
            assert "TestOS" in rendered

    @pytest.mark.asyncio
    async def test_dry_run_shown(self):
        from textual.app import App, ComposeResult

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield StatusBar(
                    is_admin=False, dry_run=True, platform_name="TestOS"
                )

        app = TestApp()
        async with app.run_test() as pilot:
            bar = app.query_one("#status-bar", StatusBar)
            rendered = str(bar.content)
            assert "DRY RUN" in rendered

    @pytest.mark.asyncio
    async def test_admin_shown(self):
        from textual.app import App, ComposeResult

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield StatusBar(
                    is_admin=True, dry_run=False, platform_name="TestOS"
                )

        app = TestApp()
        async with app.run_test() as pilot:
            bar = app.query_one("#status-bar", StatusBar)
            rendered = str(bar.content)
            assert "Admin" in rendered

    @pytest.mark.asyncio
    async def test_set_dry_run(self):
        from textual.app import App, ComposeResult

        class TestApp(App):
            def compose(self) -> ComposeResult:
                yield StatusBar(
                    is_admin=False, dry_run=False, platform_name="TestOS"
                )

        app = TestApp()
        async with app.run_test() as pilot:
            bar = app.query_one("#status-bar", StatusBar)
            bar.set_dry_run(True)
            rendered = str(bar.content)
            assert "DRY RUN" in rendered
