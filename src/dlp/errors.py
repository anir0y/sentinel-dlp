"""DLP-specific exceptions for clean error handling."""

from __future__ import annotations


class DLPError(Exception):
    """Base exception for all DLP operations."""


class PlatformError(DLPError):
    """Error from OS-level platform operations."""


class USBEnumerationError(PlatformError):
    """Failed to enumerate USB devices."""


class RegistryError(PlatformError):
    """Failed to read/write Windows registry."""


class StorageMonitorError(PlatformError):
    """Error in the storage monitor loop."""
