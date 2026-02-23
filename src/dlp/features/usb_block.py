"""USB storage block orchestration layer."""

from __future__ import annotations

import logging

from dlp.audit.rollback import RollbackJournal
from dlp.config import DLPConfig
from dlp.features.usb_whitelist import is_device_whitelisted
from dlp.platform.base import USBManagerBase

logger = logging.getLogger(__name__)


class USBBlockController:
    """Orchestrates USB blocking with whitelist awareness and rollback."""

    def __init__(
        self,
        manager: USBManagerBase,
        config: DLPConfig,
        rollback: RollbackJournal,
    ) -> None:
        self.manager = manager
        self.config = config
        self.rollback = rollback

    def block_all_storage(self) -> str:
        """Block all USB mass storage. Returns status message."""
        if self.manager.is_mass_storage_blocked():
            return "USB mass storage is already blocked."

        self.rollback.push(
            description="Block all USB mass storage",
            undo_fn=self.manager.unblock_mass_storage,
            feature="usb_block",
        )
        self.manager.block_mass_storage()
        logger.info("USB mass storage blocked")
        return "USB mass storage blocked."

    def unblock_all_storage(self) -> str:
        """Unblock all USB mass storage. Returns status message."""
        if not self.manager.is_mass_storage_blocked():
            return "USB mass storage is already enabled."

        self.rollback.push(
            description="Unblock all USB mass storage",
            undo_fn=self.manager.block_mass_storage,
            feature="usb_block",
        )
        self.manager.unblock_mass_storage()
        logger.info("USB mass storage unblocked")
        return "USB mass storage unblocked."

    def enforce_whitelist(self) -> list[str]:
        """Block non-whitelisted devices, allow whitelisted ones.

        Returns list of action descriptions.
        """
        if not self.config.usb.whitelist_enabled:
            return ["Whitelist enforcement is disabled."]

        actions: list[str] = []
        devices = self.manager.enumerate_devices()

        for dev in devices:
            if dev.device_class != "mass_storage":
                continue

            whitelisted = is_device_whitelisted(
                dev.vendor_id,
                dev.product_id,
                dev.serial_number,
                self.config.usb.whitelist,
            )

            if whitelisted:
                self.manager.allow_device(dev.vendor_id, dev.product_id)
                actions.append(
                    f"ALLOWED: {dev.product_name} "
                    f"(VID:{dev.vendor_id} PID:{dev.product_id})"
                )
            else:
                self.manager.block_device(dev.vendor_id, dev.product_id)
                actions.append(
                    f"BLOCKED: {dev.product_name} "
                    f"(VID:{dev.vendor_id} PID:{dev.product_id})"
                )

        if not actions:
            actions.append("No mass storage devices found.")

        return actions
