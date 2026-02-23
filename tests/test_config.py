"""Tests for configuration loading and validation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from dlp.config import DLPConfig, WhitelistEntry


def test_default_config():
    config = DLPConfig()
    assert config.usb.block_mass_storage is False
    assert config.usb.whitelist_enabled is False
    assert config.usb.whitelist == []
    assert config.programs.enabled is False
    assert config.programs.blocked_paths == []


def test_config_with_whitelist():
    config = DLPConfig(
        usb={
            "whitelist_enabled": True,
            "whitelist": [
                {"vendor_id": "0781", "product_id": "5583", "label": "SanDisk"},
            ],
        }
    )
    assert config.usb.whitelist_enabled is True
    assert len(config.usb.whitelist) == 1
    assert config.usb.whitelist[0].vendor_id == "0781"
    assert config.usb.whitelist[0].label == "SanDisk"


def test_whitelist_entry_optional_serial():
    entry = WhitelistEntry(vendor_id="0781", product_id="5583")
    assert entry.serial_number is None
    assert entry.label == ""


def test_whitelist_entry_with_serial():
    entry = WhitelistEntry(
        vendor_id="0781",
        product_id="5583",
        serial_number="ABC123",
        label="My Drive",
    )
    assert entry.serial_number == "ABC123"
    assert entry.label == "My Drive"


def test_config_from_toml():
    toml_content = b"""
[usb]
block_mass_storage = true
whitelist_enabled = true

[[usb.whitelist]]
vendor_id = "0781"
product_id = "5583"
label = "SanDisk"

[programs]
enabled = false
blocked_paths = []
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(toml_content)
        f.flush()
        config = DLPConfig.from_toml(Path(f.name))

    assert config.usb.block_mass_storage is True
    assert config.usb.whitelist_enabled is True
    assert len(config.usb.whitelist) == 1
    assert config.usb.whitelist[0].vendor_id == "0781"


def test_config_model_dump():
    config = DLPConfig(
        usb={
            "whitelist": [
                {"vendor_id": "0781", "product_id": "5583"},
            ],
        }
    )
    data = config.model_dump()
    assert "usb" in data
    assert "programs" in data
    assert len(data["usb"]["whitelist"]) == 1


# ---------------------------------------------------------------------------
# New config sub-models
# ---------------------------------------------------------------------------


def test_new_sections_have_defaults():
    """All new config sections should have sensible defaults."""
    config = DLPConfig()
    assert config.monitoring.poll_interval_seconds == 2.0
    assert config.monitoring.hotplug_poll_interval_seconds == 3.0
    assert config.monitoring.max_rollback_entries == 100
    assert config.notifications.enabled is False
    assert config.notifications.on_ducky_detected is True
    assert config.network.enabled is False
    assert config.network.upload_threshold_mb == 100.0
    assert config.clipboard.enabled is False
    assert config.clipboard.patterns == []
    assert config.file_activity.enabled is False
    assert config.file_activity.bulk_copy_threshold_files == 50
    assert config.bluetooth.enabled is False
    assert config.logging.level == "WARNING"
    assert config.logging.file is None


def test_backward_compatible_toml():
    """Existing TOML without new sections should still load."""
    old_toml = b"""
[usb]
block_mass_storage = true
whitelist_enabled = false

[programs]
enabled = false
blocked_paths = []
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(old_toml)
        f.flush()
        config = DLPConfig.from_toml(Path(f.name))

    assert config.usb.block_mass_storage is True
    # New sections should get defaults
    assert config.monitoring.poll_interval_seconds == 2.0
    assert config.notifications.enabled is False
    assert config.network.enabled is False
    assert config.logging.level == "WARNING"


def test_full_config_toml():
    """TOML with all sections should load correctly."""
    full_toml = b"""
[usb]
block_mass_storage = false
whitelist_enabled = true

[[usb.whitelist]]
vendor_id = "0781"
product_id = "5583"
label = "SanDisk"

[programs]
enabled = false
blocked_paths = []

[monitoring]
poll_interval_seconds = 1.0
hotplug_poll_interval_seconds = 5.0
max_rollback_entries = 50

[notifications]
enabled = true
on_ducky_detected = true
on_blocked_usb_inserted = false

[network]
enabled = true
upload_threshold_mb = 200.0
check_interval_seconds = 10.0

[clipboard]
enabled = true
patterns = ["\\\\bSSN\\\\b"]

[file_activity]
enabled = true
watch_external_volumes = false
bulk_copy_threshold_files = 100
check_interval_seconds = 3.0

[bluetooth]
enabled = true

[logging]
level = "DEBUG"
file = "/tmp/dlp.log"
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
        f.write(full_toml)
        f.flush()
        config = DLPConfig.from_toml(Path(f.name))

    assert config.monitoring.poll_interval_seconds == 1.0
    assert config.monitoring.max_rollback_entries == 50
    assert config.notifications.enabled is True
    assert config.notifications.on_blocked_usb_inserted is False
    assert config.network.enabled is True
    assert config.network.upload_threshold_mb == 200.0
    assert config.clipboard.enabled is True
    assert config.file_activity.bulk_copy_threshold_files == 100
    assert config.bluetooth.enabled is True
    assert config.logging.level == "DEBUG"
    assert config.logging.file == "/tmp/dlp.log"


def test_config_dump_includes_new_sections():
    """model_dump() should include all new config sections."""
    config = DLPConfig()
    data = config.model_dump()
    assert "monitoring" in data
    assert "notifications" in data
    assert "network" in data
    assert "clipboard" in data
    assert "file_activity" in data
    assert "bluetooth" in data
    assert "logging" in data
