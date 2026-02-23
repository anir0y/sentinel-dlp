"""Tests for policy export/import."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from dlp.config import DLPConfig
from dlp.features.policy_export import export_policy, import_policy


class TestPolicyExport:
    """Tests for dlp.features.policy_export export/import functions."""

    def test_export_creates_json_file(self):
        config = DLPConfig()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        export_policy(config, tmp_path)

        assert tmp_path.exists()
        with open(tmp_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        tmp_path.unlink(missing_ok=True)

    def test_import_reads_json(self):
        config = DLPConfig()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        export_policy(config, tmp_path)
        imported = import_policy(tmp_path)

        assert imported is not None
        assert type(imported).__name__ == "DLPConfig"
        tmp_path.unlink(missing_ok=True)

    def test_round_trip(self):
        config = DLPConfig()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        export_policy(config, tmp_path)
        imported = import_policy(tmp_path)

        assert config.model_dump() == imported.model_dump()
        tmp_path.unlink(missing_ok=True)

    def test_import_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as tmp:
            tmp.write("{not valid json!!!")
            tmp_path = Path(tmp.name)

        with pytest.raises(ValueError, match="Invalid JSON"):
            import_policy(tmp_path)

        tmp_path.unlink(missing_ok=True)

    def test_import_partial_config(self):
        # Write JSON with only a partial section
        partial = {"usb": {"block_mass_storage": True}}

        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w"
        ) as tmp:
            json.dump(partial, tmp)
            tmp_path = Path(tmp.name)

        imported = import_policy(tmp_path)

        assert imported is not None
        assert imported.usb.block_mass_storage is True
        # Other sections should get their defaults
        assert imported.network.enabled is False
        tmp_path.unlink(missing_ok=True)

    def test_import_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            import_policy(Path("/tmp/does-not-exist-dlp-test.json"))
