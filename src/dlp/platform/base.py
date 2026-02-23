"""Abstract base classes for platform-specific DLP operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class USBDeviceInfo:
    """Information about a connected USB device."""

    vendor_id: str
    product_id: str
    serial_number: str
    manufacturer: str
    product_name: str
    device_class: str  # "mass_storage", "hid", "hub", "audio", "other"
    device_path: str  # OS-specific identifier


@dataclass
class BlockRule:
    """A program blocking rule."""

    rule_id: str
    path_pattern: str
    description: str = ""


class USBManagerBase(ABC):
    """Platform-specific USB operations."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    @abstractmethod
    def enumerate_devices(self) -> list[USBDeviceInfo]:
        """List all connected USB devices."""

    @abstractmethod
    def enumerate_hid_devices(self) -> list[USBDeviceInfo]:
        """List only HID-class devices."""

    @abstractmethod
    def block_mass_storage(self) -> None:
        """Globally block USB mass storage."""

    @abstractmethod
    def unblock_mass_storage(self) -> None:
        """Re-enable USB mass storage."""

    @abstractmethod
    def is_mass_storage_blocked(self) -> bool:
        """Check current block status."""

    @abstractmethod
    def block_device(self, vendor_id: str, product_id: str) -> None:
        """Block a specific device by VID/PID."""

    @abstractmethod
    def allow_device(self, vendor_id: str, product_id: str) -> None:
        """Remove a specific device from the block list."""

    @abstractmethod
    def get_blocked_devices(self) -> list[tuple[str, str]]:
        """Return list of (vendor_id, product_id) that are blocked."""


class ProgramBlockerBase(ABC):
    """Program execution restriction (Windows only)."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    @abstractmethod
    def block_path(self, path_pattern: str, description: str = "") -> str:
        """Block executables matching pattern. Returns rule ID."""

    @abstractmethod
    def unblock_path(self, rule_id: str) -> None:
        """Remove a block rule by ID."""

    @abstractmethod
    def list_rules(self) -> list[BlockRule]:
        """List all active restriction rules."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the program blocking feature is available."""
