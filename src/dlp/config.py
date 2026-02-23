"""Configuration models for DLP policies."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel


class WhitelistEntry(BaseModel):
    """A single whitelisted USB device."""

    vendor_id: str
    product_id: str
    serial_number: str | None = None
    label: str = ""


class USBPolicy(BaseModel):
    """USB storage blocking policy."""

    block_mass_storage: bool = False
    whitelist_enabled: bool = False
    whitelist: list[WhitelistEntry] = []


class ProgramPolicy(BaseModel):
    """Program execution restriction policy (Windows only)."""

    enabled: bool = False
    blocked_paths: list[str] = []


class MonitoringConfig(BaseModel):
    """Polling and monitoring settings."""

    poll_interval_seconds: float = 2.0
    hotplug_poll_interval_seconds: float = 3.0
    max_rollback_entries: int = 100


class NotificationConfig(BaseModel):
    """Desktop notification settings."""

    enabled: bool = False
    on_ducky_detected: bool = True
    on_blocked_usb_inserted: bool = True


class NetworkPolicy(BaseModel):
    """Network exfiltration detection config."""

    enabled: bool = False
    upload_threshold_mb: float = 100.0
    check_interval_seconds: float = 5.0


class ClipboardPolicy(BaseModel):
    """Clipboard monitoring config."""

    enabled: bool = False
    patterns: list[str] = []


class FileActivityPolicy(BaseModel):
    """File activity monitoring config."""

    enabled: bool = False
    watch_external_volumes: bool = True
    bulk_copy_threshold_files: int = 50
    check_interval_seconds: float = 5.0


class BluetoothPolicy(BaseModel):
    """Bluetooth monitoring config."""

    enabled: bool = False


class LoggingConfig(BaseModel):
    """Application logging settings."""

    level: str = "WARNING"
    file: str | None = None
    audit_log_path: str | None = None


class DLPConfig(BaseModel):
    """Root configuration model."""

    usb: USBPolicy = USBPolicy()
    programs: ProgramPolicy = ProgramPolicy()
    monitoring: MonitoringConfig = MonitoringConfig()
    notifications: NotificationConfig = NotificationConfig()
    network: NetworkPolicy = NetworkPolicy()
    clipboard: ClipboardPolicy = ClipboardPolicy()
    file_activity: FileActivityPolicy = FileActivityPolicy()
    bluetooth: BluetoothPolicy = BluetoothPolicy()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def from_toml(cls, path: Path) -> DLPConfig:
        """Load config from a TOML file."""
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.model_validate(data)

    def to_toml(self, path: Path) -> None:
        """Save config to a TOML file."""
        import tomli_w

        with open(path, "wb") as f:
            tomli_w.dump(self.model_dump(), f)
