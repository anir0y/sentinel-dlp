"""DLP TUI Application - main Textual app."""

from __future__ import annotations

import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Header, Input, TabbedContent, TabPane

from dlp.audit.logger import log_action, read_recent_entries
from dlp.audit.rollback import RollbackJournal
from dlp.config import DLPConfig, WhitelistEntry
from dlp.errors import PlatformError
from dlp.features.hid_fingerprint import fingerprint_devices
from dlp.features.program_block import ProgramBlockController
from dlp.features.usb_block import USBBlockController
from dlp.platform import get_platform_name, get_program_blocker, get_usb_manager, is_admin
from dlp.ui.screens.audit_viewer import AuditViewerScreen
from dlp.ui.screens.bluetooth_viewer import BluetoothViewerScreen
from dlp.ui.screens.dashboard import DashboardScreen
from dlp.ui.screens.hid_viewer import HIDViewerScreen
from dlp.ui.screens.network_monitor import NetworkMonitorScreen
from dlp.ui.screens.program_policy import ProgramPolicyScreen
from dlp.ui.screens.rollback_viewer import RollbackViewerScreen
from dlp.ui.screens.usb_manager import USBManagerScreen
from dlp.ui.widgets.confirm_modal import ConfirmModal
from dlp.ui.widgets.device_table import DeviceTable
from dlp.ui.widgets.status_bar import StatusBar

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default.toml"


class DLPApp(App):
    """DLP Control Panel TUI Application."""

    CSS_PATH = "ui/styles/app.tcss"
    TITLE = "DLP Control Panel"

    BINDINGS = [
        Binding("d", "switch_tab('dashboard')", "Dashboard"),
        Binding("u", "switch_tab('usb')", "USB Manager"),
        Binding("h", "switch_tab('hid')", "HID Viewer"),
        Binding("p", "switch_tab('programs')", "Programs"),
        Binding("n", "switch_tab('network')", "Network"),
        Binding("b", "switch_tab('bluetooth')", "Bluetooth"),
        Binding("a", "switch_tab('audit')", "Audit Log"),
        Binding("o", "switch_tab('rollback')", "Rollback"),
        Binding("z", "undo", "Undo"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("s", "save_config", "Save Config"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, dry_run: bool = False, config: DLPConfig | None = None) -> None:
        super().__init__()
        self.dry_run = dry_run
        self._admin = is_admin()

        # Load config (accept pre-loaded config or load from file)
        if config is not None:
            self.config = config
        elif CONFIG_PATH.exists():
            self.config = DLPConfig.from_toml(CONFIG_PATH)
        else:
            self.config = DLPConfig()

        # Initialize platform layer
        self.usb_manager = get_usb_manager(dry_run=dry_run)
        self.rollback = RollbackJournal(
            max_entries=self.config.monitoring.max_rollback_entries
        )
        self.usb_controller = USBBlockController(
            manager=self.usb_manager,
            config=self.config,
            rollback=self.rollback,
        )
        blocker = get_program_blocker(dry_run=dry_run)
        self.program_controller = ProgramBlockController(
            blocker=blocker,
            rollback=self.rollback,
        )

        # Store fingerprints for detail lookup
        self._fingerprints: list = []

        # Hotplug tracking
        self._last_device_paths: set[str] = set()

        # Background monitors (lazily initialised when config enables them)
        self._network_monitor = None
        self._clipboard_last_text: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar(
            is_admin=self._admin,
            dry_run=self.dry_run,
            platform_name=get_platform_name(),
        )
        with TabbedContent():
            with TabPane("Dashboard", id="tab-dashboard"):
                yield DashboardScreen(id="dashboard")
            with TabPane("USB Manager", id="tab-usb"):
                yield USBManagerScreen(id="usb-manager")
            with TabPane("HID Viewer", id="tab-hid"):
                yield HIDViewerScreen(id="hid-viewer")
            with TabPane("Programs", id="tab-programs"):
                yield ProgramPolicyScreen(id="program-policy")
            with TabPane("Network", id="tab-network"):
                yield NetworkMonitorScreen(id="network-monitor")
            with TabPane("Bluetooth", id="tab-bluetooth"):
                yield BluetoothViewerScreen(id="bluetooth-viewer")
            with TabPane("Audit Log", id="tab-audit"):
                yield AuditViewerScreen(id="audit-viewer")
            with TabPane("Rollback", id="tab-rollback"):
                yield RollbackViewerScreen(id="rollback-viewer")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize state after mount."""
        self._refresh_dashboard()
        self._refresh_usb_status()
        self._refresh_whitelist_display()
        self._start_background_monitors()

    # ------------------------------------------------------------------
    # Background monitor setup
    # ------------------------------------------------------------------

    def _start_background_monitors(self) -> None:
        """Start timers for hotplug detection and optional background monitors."""
        # Hotplug polling
        interval = self.config.monitoring.hotplug_poll_interval_seconds
        self.set_interval(interval, self._check_hotplug)

        # Network monitoring
        if self.config.network.enabled:
            try:
                from dlp.features.network_monitor import NetworkMonitor

                self._network_monitor = NetworkMonitor(
                    threshold_mb=self.config.network.upload_threshold_mb
                )
                self.set_interval(
                    self.config.network.check_interval_seconds,
                    self._check_network,
                )
                net_screen = self.query_one("#network-monitor", NetworkMonitorScreen)
                net_screen.update_status("[green]Network monitoring active[/]")
            except Exception:
                logger.debug("Failed to start network monitor", exc_info=True)

        # Clipboard monitoring
        if self.config.clipboard.enabled:
            self.set_interval(
                self.config.monitoring.poll_interval_seconds,
                self._check_clipboard,
            )

        # File activity monitoring
        if self.config.file_activity.enabled:
            self.set_interval(
                self.config.file_activity.check_interval_seconds,
                self._check_file_activity,
            )

    def _check_hotplug(self) -> None:
        """Diff device_path sets to detect USB hotplug events."""
        try:
            devices = self.usb_manager.enumerate_devices()
        except Exception:
            return
        current = {d.device_path for d in devices}
        if not self._last_device_paths:
            self._last_device_paths = current
            return

        added = current - self._last_device_paths
        removed = self._last_device_paths - current
        self._last_device_paths = current

        if added or removed:
            parts: list[str] = []
            if added:
                parts.append(f"{len(added)} added")
            if removed:
                parts.append(f"{len(removed)} removed")
            self.notify(f"USB change: {', '.join(parts)}")
            self._refresh_dashboard()
            self._refresh_usb_status()

            # Notify on blocked USB insertion if enabled
            if added and self.config.notifications.on_blocked_usb_inserted:
                self._maybe_notify_blocked_usb(devices)

    def _maybe_notify_blocked_usb(self, devices: list) -> None:
        """Send desktop notification if a newly inserted device should be blocked."""
        if not self.config.notifications.enabled:
            return
        try:
            from dlp.features.notifier import send_notification

            fps = fingerprint_devices(devices)
            for fp in fps:
                if fp.ducky.is_ducky:
                    send_notification(
                        "DLP ALERT: Potential BadUSB",
                        f"Device {fp.device.product_name} (VID:{fp.device.vendor_id}) "
                        f"flagged as {fp.ducky.confidence} confidence.",
                    )
        except Exception:
            logger.debug("Hotplug notification failed", exc_info=True)

    def _check_network(self) -> None:
        """Run periodic network exfiltration check."""
        if not self._network_monitor:
            return
        try:
            alerts = self._network_monitor.check()
            if alerts:
                net_screen = self.query_one("#network-monitor", NetworkMonitorScreen)
                for alert in alerts:
                    msg = (
                        f"[bold red]ALERT[/] {alert.interface}: "
                        f"{alert.mb_sent:.1f} MB sent in {alert.duration:.0f}s "
                        f"(threshold: {alert.threshold_mb:.0f} MB)"
                    )
                    net_screen.append_alert(msg)
                    log_action(
                        "network", "threshold_exceeded",
                        params={"interface": alert.interface, "mb_sent": alert.mb_sent},
                        dry_run=self.dry_run,
                    )
                    if self.config.notifications.enabled:
                        try:
                            from dlp.features.notifier import send_notification

                            send_notification(
                                "DLP: Network Upload Alert",
                                f"{alert.interface}: {alert.mb_sent:.1f} MB sent",
                            )
                        except Exception:
                            pass
        except Exception:
            logger.debug("Network check failed", exc_info=True)

    def _check_clipboard(self) -> None:
        """Run periodic clipboard content scan."""
        try:
            from dlp.features.clipboard_monitor import get_clipboard_text, scan_clipboard

            text = get_clipboard_text()
            if not text or text == self._clipboard_last_text:
                return
            self._clipboard_last_text = text

            # Config patterns is list[str]; scan_clipboard expects dict[str, str] | None
            custom_dict = None
            if self.config.clipboard.patterns:
                custom_dict = {
                    f"custom_{i}": pat
                    for i, pat in enumerate(self.config.clipboard.patterns)
                }
            alerts = scan_clipboard(text, patterns=custom_dict)
            for alert in alerts:
                log_action(
                    "clipboard", "sensitive_detected",
                    params={"pattern": alert.pattern_name, "preview": alert.preview},
                    dry_run=self.dry_run,
                )
                self.notify(
                    f"Clipboard: {alert.pattern_name} detected",
                    severity="warning",
                )
        except Exception:
            logger.debug("Clipboard check failed", exc_info=True)

    def _check_file_activity(self) -> None:
        """Run periodic file activity check on external volumes."""
        try:
            from dlp.features.file_monitor import check_bulk_copy, get_external_volumes

            volumes = get_external_volumes()
            if not volumes:
                return
            alerts = check_bulk_copy(
                volumes=volumes,
                threshold=self.config.file_activity.bulk_copy_threshold_files,
            )
            for alert in alerts:
                log_action(
                    "file_activity", "bulk_copy_detected",
                    params={
                        "volume": str(alert.volume_path),
                        "file_count": alert.file_count,
                    },
                    dry_run=self.dry_run,
                )
                self.notify(
                    f"File activity: {alert.file_count} files on {Path(alert.volume_path).name}",
                    severity="warning",
                )
        except Exception:
            logger.debug("File activity check failed", exc_info=True)

    # ------------------------------------------------------------------
    # Dashboard / USB refresh
    # ------------------------------------------------------------------

    def _refresh_dashboard(self) -> None:
        dashboard = self.query_one("#dashboard", DashboardScreen)
        try:
            blocked = self.usb_manager.is_mass_storage_blocked()
        except PlatformError as e:
            blocked = False
            logger.warning("Could not check USB status: %s", e)
            self.notify(f"USB status check failed: {e}", severity="warning")
        except Exception:
            blocked = False
            logger.exception("Unexpected error checking USB status")
        dashboard.update_usb_status(blocked, self.dry_run)
        dashboard.update_whitelist_status(
            self.config.usb.whitelist_enabled,
            len(self.config.usb.whitelist),
        )
        dashboard.update_program_status(
            self.program_controller.available,
            len(self.program_controller.list_blocked()),
        )

    def _refresh_usb_status(self) -> None:
        usb_screen = self.query_one("#usb-manager", USBManagerScreen)
        try:
            blocked = self.usb_manager.is_mass_storage_blocked()
        except PlatformError as e:
            blocked = False
            logger.warning("Could not check USB status: %s", e)
        except Exception:
            blocked = False
            logger.exception("Unexpected error checking USB status")
        usb_screen.update_block_status(blocked, self.dry_run)

    def _refresh_whitelist_display(self) -> None:
        usb_screen = self.query_one("#usb-manager", USBManagerScreen)
        entries = [e.model_dump() for e in self.config.usb.whitelist]
        usb_screen.update_whitelist_display(entries)

    # --- Button handlers ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        handlers = {
            # Existing
            "btn-block-usb": self._handle_block_usb,
            "btn-unblock-usb": self._handle_unblock_usb,
            "btn-enforce-whitelist": self._handle_enforce_whitelist,
            "btn-add-whitelist": self._handle_add_whitelist,
            "btn-remove-whitelist": self._handle_remove_whitelist,
            "btn-scan-hid": self._handle_scan_hid,
            "btn-scan-all": self._handle_scan_all,
            "btn-block-program": self._handle_block_program,
            "btn-remove-rule": self._handle_remove_rule,
            # HID viewer actions
            "btn-block-hid-device": self._handle_block_hid_device,
            "btn-whitelist-hid-device": self._handle_whitelist_hid_device,
            # New feature tabs
            "btn-check-network": self._handle_check_network,
            "btn-scan-bluetooth": self._handle_scan_bluetooth,
            "btn-refresh-audit": self._handle_refresh_audit,
            "btn-refresh-rollback": self._handle_refresh_rollback,
            "btn-undo-selected": self._handle_undo_selected,
            # Dashboard actions
            "btn-save-config": self._handle_save_config,
            "btn-export-policy": self._handle_export_policy,
            "btn-import-policy": self._handle_import_policy,
            # Modal buttons
            "confirm-yes": lambda: None,
            "confirm-no": lambda: None,
        }
        handler = handlers.get(button_id)
        if handler:
            handler()

    # ------------------------------------------------------------------
    # USB handlers (existing)
    # ------------------------------------------------------------------

    def _handle_block_usb(self) -> None:
        if not self._admin and not self.dry_run:
            self.notify("Admin privileges required", severity="error")
            return

        def do_block(confirmed: bool) -> None:
            if not confirmed:
                return
            msg = self.usb_controller.block_all_storage()
            log_action("usb_block", "block_all", dry_run=self.dry_run)
            usb_screen = self.query_one("#usb-manager", USBManagerScreen)
            usb_screen.append_log(msg)
            self._refresh_usb_status()
            self._refresh_dashboard()
            self.notify(msg)

        self.push_screen(
            ConfirmModal(
                "Block USB Storage",
                "This will disable all USB mass storage devices.\nAre you sure?",
            ),
            do_block,
        )

    def _handle_unblock_usb(self) -> None:
        if not self._admin and not self.dry_run:
            self.notify("Admin privileges required", severity="error")
            return
        msg = self.usb_controller.unblock_all_storage()
        log_action("usb_block", "unblock_all", dry_run=self.dry_run)
        usb_screen = self.query_one("#usb-manager", USBManagerScreen)
        usb_screen.append_log(msg)
        self._refresh_usb_status()
        self._refresh_dashboard()
        self.notify(msg)

    def _handle_enforce_whitelist(self) -> None:
        if not self._admin and not self.dry_run:
            self.notify("Admin privileges required", severity="error")
            return
        actions = self.usb_controller.enforce_whitelist()
        usb_screen = self.query_one("#usb-manager", USBManagerScreen)
        for action in actions:
            usb_screen.append_log(action)
            log_action("usb_whitelist", "enforce", params={"action": action}, dry_run=self.dry_run)
        self.notify(f"Whitelist enforced: {len(actions)} actions")

    def _handle_add_whitelist(self) -> None:
        usb_screen = self.query_one("#usb-manager", USBManagerScreen)
        vid_input = self.query_one("#input-vid", Input)
        pid_input = self.query_one("#input-pid", Input)
        serial_input = self.query_one("#input-serial", Input)
        label_input = self.query_one("#input-label", Input)

        vid = vid_input.value.strip()
        pid = pid_input.value.strip()
        serial = serial_input.value.strip() or None
        label = label_input.value.strip()

        if not vid or not pid:
            self.notify("Vendor ID and Product ID are required", severity="error")
            return

        entry = WhitelistEntry(
            vendor_id=vid,
            product_id=pid,
            serial_number=serial,
            label=label,
        )
        self.config.usb.whitelist.append(entry)
        self.config.usb.whitelist_enabled = True

        # Clear inputs
        vid_input.value = ""
        pid_input.value = ""
        serial_input.value = ""
        label_input.value = ""

        self._refresh_whitelist_display()
        self._refresh_dashboard()
        log_action("usb_whitelist", "add_entry", params=entry.model_dump(), dry_run=self.dry_run)
        usb_screen.append_log(f"Added to whitelist: VID:{vid} PID:{pid} {label}")
        self.notify(f"Whitelist entry added: {label or f'VID:{vid}'}")

    def _handle_remove_whitelist(self) -> None:
        """Remove a whitelist entry by 1-based index."""
        idx_input = self.query_one("#input-remove-whitelist-idx", Input)
        idx_str = idx_input.value.strip()
        if not idx_str.isdigit():
            self.notify("Enter a valid entry number", severity="error")
            return
        idx = int(idx_str) - 1
        if idx < 0 or idx >= len(self.config.usb.whitelist):
            self.notify("Entry number out of range", severity="error")
            return
        removed = self.config.usb.whitelist.pop(idx)
        idx_input.value = ""
        self._refresh_whitelist_display()
        self._refresh_dashboard()
        log_action("usb_whitelist", "remove_entry", params=removed.model_dump(), dry_run=self.dry_run)
        usb_screen = self.query_one("#usb-manager", USBManagerScreen)
        usb_screen.append_log(f"Removed whitelist entry #{idx + 1}: VID:{removed.vendor_id}")
        self.notify(f"Whitelist entry removed: {removed.label or removed.vendor_id}")

    # ------------------------------------------------------------------
    # HID handlers
    # ------------------------------------------------------------------

    def _handle_scan_hid(self) -> None:
        hid_screen = self.query_one("#hid-viewer", HIDViewerScreen)
        hid_screen.update_scan_status("Scanning HID devices...")
        try:
            devices = self.usb_manager.enumerate_hid_devices()
            self._fingerprints = fingerprint_devices(devices)
            hid_screen.load_devices(self._fingerprints)
            dashboard = self.query_one("#dashboard", DashboardScreen)
            dashboard.update_hid_count(len(self._fingerprints))
            log_action("hid", "scan_hid", params={"count": len(devices)}, dry_run=self.dry_run)
        except Exception as e:
            hid_screen.update_scan_status(f"[red]Error: {e}[/]")
            log_action("hid", "scan_hid", success=False, error=str(e), dry_run=self.dry_run)

    def _handle_scan_all(self) -> None:
        hid_screen = self.query_one("#hid-viewer", HIDViewerScreen)
        hid_screen.update_scan_status("Scanning all USB devices...")
        try:
            devices = self.usb_manager.enumerate_devices()
            self._fingerprints = fingerprint_devices(devices)
            hid_screen.load_devices(self._fingerprints)
            dashboard = self.query_one("#dashboard", DashboardScreen)
            dashboard.update_hid_count(len(self._fingerprints))
            log_action("hid", "scan_all", params={"count": len(devices)}, dry_run=self.dry_run)
        except Exception as e:
            hid_screen.update_scan_status(f"[red]Error: {e}[/]")
            log_action("hid", "scan_all", success=False, error=str(e), dry_run=self.dry_run)

    def _handle_block_hid_device(self) -> None:
        """Block the currently selected device in HID table."""
        table = self.query_one("#hid-table", DeviceTable)
        fp = table.get_selected_fingerprint()
        if not fp:
            self.notify("No device selected", severity="error")
            return

        def do_block(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.usb_manager.block_device(fp.device.vendor_id, fp.device.product_id)
                self.rollback.push(
                    f"Blocked device VID:{fp.device.vendor_id} PID:{fp.device.product_id}",
                    lambda v=fp.device.vendor_id, p=fp.device.product_id: self.usb_manager.allow_device(v, p),
                    "usb_block",
                )
                log_action(
                    "usb_block", "block_device",
                    params={"vid": fp.device.vendor_id, "pid": fp.device.product_id},
                    dry_run=self.dry_run,
                )
                self.notify(f"Blocked: VID:{fp.device.vendor_id} PID:{fp.device.product_id}")
            except Exception as e:
                self.notify(f"Block failed: {e}", severity="error")

        self.push_screen(
            ConfirmModal(
                "Block Device",
                f"Block device: {fp.device.product_name}\n"
                f"VID:{fp.device.vendor_id} PID:{fp.device.product_id}\n\nAre you sure?",
            ),
            do_block,
        )

    def _handle_whitelist_hid_device(self) -> None:
        """Whitelist the currently selected device in HID table."""
        table = self.query_one("#hid-table", DeviceTable)
        fp = table.get_selected_fingerprint()
        if not fp:
            self.notify("No device selected", severity="error")
            return
        entry = WhitelistEntry(
            vendor_id=fp.device.vendor_id,
            product_id=fp.device.product_id,
            serial_number=fp.device.serial_number or None,
            label=fp.device.product_name,
        )
        self.config.usb.whitelist.append(entry)
        self.config.usb.whitelist_enabled = True
        self._refresh_whitelist_display()
        self._refresh_dashboard()
        log_action("usb_whitelist", "add_from_hid", params=entry.model_dump(), dry_run=self.dry_run)
        self.notify(f"Whitelisted: {fp.device.product_name}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show device details when a row is selected in HID table."""
        if event.data_table.id != "hid-table":
            return
        table = self.query_one("#hid-table", DeviceTable)
        fp = table.get_selected_fingerprint()
        if fp:
            hid_screen = self.query_one("#hid-viewer", HIDViewerScreen)
            hid_screen.show_device_details(fp)

            # Ducky notification
            if fp.ducky.is_ducky and self.config.notifications.enabled and self.config.notifications.on_ducky_detected:
                try:
                    from dlp.features.notifier import send_notification

                    send_notification(
                        "DLP ALERT: BadUSB Detected",
                        f"{fp.device.product_name} flagged as {fp.ducky.confidence}",
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Program handlers
    # ------------------------------------------------------------------

    def _handle_block_program(self) -> None:
        if not self.program_controller.available and not self.dry_run:
            self.notify(self.program_controller.unavailable_reason, severity="error")
            return

        path_input = self.query_one("#input-block-path", Input)
        desc_input = self.query_one("#input-block-desc", Input)
        path_pattern = path_input.value.strip()
        description = desc_input.value.strip()

        if not path_pattern:
            self.notify("Path pattern is required", severity="error")
            return

        def do_block(confirmed: bool) -> None:
            if not confirmed:
                return
            msg = self.program_controller.block_program(path_pattern, description)
            program_screen = self.query_one("#program-policy", ProgramPolicyScreen)
            program_screen.append_log(msg)
            log_action(
                "program_block", "block_path",
                params={"path": path_pattern, "desc": description},
                dry_run=self.dry_run,
            )
            path_input.value = ""
            desc_input.value = ""
            self._refresh_program_rules()
            self._refresh_dashboard()
            self.notify(msg)

        self.push_screen(
            ConfirmModal(
                "Block Program Path",
                f"This will block execution of programs matching:\n{path_pattern}\n\nAre you sure?",
            ),
            do_block,
        )

    def _handle_remove_rule(self) -> None:
        """Remove a program block rule by ID prefix."""
        try:
            rule_input = self.query_one("#input-remove-rule-id", Input)
        except Exception:
            self.notify("Rule removal not available on this platform", severity="error")
            return

        prefix = rule_input.value.strip()
        if not prefix:
            self.notify("Enter a rule ID prefix", severity="error")
            return

        rules = self.program_controller.list_blocked()
        match = next((r for r in rules if r.rule_id.startswith(prefix)), None)
        if not match:
            self.notify(f"No rule matching prefix '{prefix}'", severity="error")
            return

        msg = self.program_controller.unblock_program(match.rule_id)
        rule_input.value = ""
        self._refresh_program_rules()
        self._refresh_dashboard()
        log_action(
            "program_block", "unblock_path",
            params={"rule_id": match.rule_id, "path": match.path_pattern},
            dry_run=self.dry_run,
        )
        program_screen = self.query_one("#program-policy", ProgramPolicyScreen)
        program_screen.append_log(msg)
        self.notify(msg)

    def _refresh_program_rules(self) -> None:
        program_screen = self.query_one("#program-policy", ProgramPolicyScreen)
        rules = self.program_controller.list_blocked()
        program_screen.update_rules_list(rules)

    # ------------------------------------------------------------------
    # Network handlers
    # ------------------------------------------------------------------

    def _handle_check_network(self) -> None:
        """Manual network exfiltration check."""
        try:
            from dlp.features.network_monitor import NetworkMonitor

            if not self._network_monitor:
                self._network_monitor = NetworkMonitor(
                    threshold_mb=self.config.network.upload_threshold_mb
                )
            alerts = self._network_monitor.check()
            net_screen = self.query_one("#network-monitor", NetworkMonitorScreen)
            if alerts:
                for alert in alerts:
                    msg = (
                        f"[bold red]ALERT[/] {alert.interface}: "
                        f"{alert.mb_sent:.1f} MB sent in {alert.duration:.0f}s"
                    )
                    net_screen.append_alert(msg)
                net_screen.update_status(f"[red]{len(alerts)} alerts detected[/]")
            else:
                net_screen.update_status("[green]No anomalies detected[/]")
        except ImportError:
            self.notify("psutil required for network monitoring", severity="error")
        except Exception as e:
            self.notify(f"Network check error: {e}", severity="error")

    # ------------------------------------------------------------------
    # Bluetooth handlers
    # ------------------------------------------------------------------

    def _handle_scan_bluetooth(self) -> None:
        """Enumerate Bluetooth devices."""
        bt_screen = self.query_one("#bluetooth-viewer", BluetoothViewerScreen)
        bt_screen.update_scan_status("Scanning Bluetooth devices...")
        try:
            from dlp.features.bluetooth_monitor import enumerate_bluetooth_devices

            devices = enumerate_bluetooth_devices()
            bt_screen.load_devices(devices)
            bt_screen.update_scan_status(f"Found {len(devices)} Bluetooth devices")
            log_action("bluetooth", "scan", params={"count": len(devices)}, dry_run=self.dry_run)
        except Exception as e:
            bt_screen.update_scan_status(f"[red]Error: {e}[/]")
            log_action("bluetooth", "scan", success=False, error=str(e), dry_run=self.dry_run)

    # ------------------------------------------------------------------
    # Audit log handlers
    # ------------------------------------------------------------------

    def _handle_refresh_audit(self) -> None:
        """Load recent audit log entries."""
        audit_screen = self.query_one("#audit-viewer", AuditViewerScreen)
        entries = read_recent_entries(count=200)
        try:
            filter_input = self.query_one("#input-audit-filter", Input)
            filter_text = filter_input.value.strip()
        except Exception:
            filter_text = ""
        audit_screen.load_entries(entries, filter_feature=filter_text)

    # ------------------------------------------------------------------
    # Rollback handlers
    # ------------------------------------------------------------------

    def _handle_refresh_rollback(self) -> None:
        """Refresh the rollback viewer."""
        rb_screen = self.query_one("#rollback-viewer", RollbackViewerScreen)
        entries = self.rollback.list_entries()
        rb_screen.load_entries(entries)

    def _handle_undo_selected(self) -> None:
        """Undo a rollback entry by 1-based index."""
        idx_input = self.query_one("#input-undo-index", Input)
        idx_str = idx_input.value.strip()
        if not idx_str.isdigit():
            self.notify("Enter a valid entry number", severity="error")
            return
        idx = int(idx_str) - 1  # 1-based UI → 0-based API
        desc = self.rollback.undo_at_index(idx)
        if desc:
            idx_input.value = ""
            self.notify(f"Undone: {desc}", severity="warning")
            log_action("rollback", "undo_selected", params={"index": idx, "action": desc}, dry_run=self.dry_run)
            self._handle_refresh_rollback()
            self._refresh_usb_status()
            self._refresh_dashboard()
        else:
            self.notify("Invalid entry number", severity="error")

    # ------------------------------------------------------------------
    # Config save / policy export-import
    # ------------------------------------------------------------------

    def _handle_save_config(self) -> None:
        """Save current config to TOML."""
        try:
            self.config.to_toml(CONFIG_PATH)
            log_action("config", "save", dry_run=self.dry_run)
            self.notify(f"Config saved to {CONFIG_PATH}")
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error")

    def _handle_export_policy(self) -> None:
        """Export policy to a JSON file."""
        try:
            path_input = self.query_one("#input-policy-path", Input)
        except Exception:
            self.notify("No path input found", severity="error")
            return
        path_str = path_input.value.strip()
        if not path_str:
            self.notify("Enter a file path for export", severity="error")
            return
        try:
            from dlp.features.policy_export import export_policy

            export_policy(self.config, Path(path_str))
            log_action("policy", "export", params={"path": path_str}, dry_run=self.dry_run)
            self.notify(f"Policy exported to {path_str}")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    def _handle_import_policy(self) -> None:
        """Import policy from a JSON file."""
        try:
            path_input = self.query_one("#input-policy-path", Input)
        except Exception:
            self.notify("No path input found", severity="error")
            return
        path_str = path_input.value.strip()
        if not path_str:
            self.notify("Enter a file path for import", severity="error")
            return
        try:
            from dlp.features.policy_export import import_policy

            imported = import_policy(Path(path_str))
            self.config = imported
            self.usb_controller._config = imported
            log_action("policy", "import", params={"path": path_str}, dry_run=self.dry_run)
            self._refresh_dashboard()
            self._refresh_usb_status()
            self._refresh_whitelist_display()
            self.notify(f"Policy imported from {path_str}")
        except Exception as e:
            self.notify(f"Import failed: {e}", severity="error")

    # --- Keybinding actions ---

    def action_switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = f"tab-{tab_id}"

    def action_undo(self) -> None:
        desc = self.rollback.undo_last()
        if desc:
            self.notify(f"Undone: {desc}", severity="warning")
            log_action("rollback", "undo", params={"action": desc}, dry_run=self.dry_run)
            self._refresh_usb_status()
            self._refresh_dashboard()
        else:
            self.notify("Nothing to undo")

    def action_refresh_all(self) -> None:
        self._refresh_dashboard()
        self._refresh_usb_status()
        self._refresh_whitelist_display()
        self._refresh_program_rules()
        self.notify("Refreshed all status")

    def action_save_config(self) -> None:
        self._handle_save_config()
