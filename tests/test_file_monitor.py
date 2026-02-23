"""Tests for file activity monitoring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGetExternalVolumes:
    """Tests for dlp.features.file_monitor external volume detection on Darwin."""

    @patch("dlp.features.file_monitor.Path")
    def test_get_external_volumes_darwin(self, mock_path_cls):
        from dlp.features.file_monitor import get_external_volumes

        # Simulate /Volumes containing Macintosh HD and two external drives
        fake_volumes = [
            MagicMock(name="Macintosh HD", spec=Path),
            MagicMock(name="USB_Drive", spec=Path),
            MagicMock(name="Backup_Disk", spec=Path),
        ]
        fake_volumes[0].name = "Macintosh HD"
        fake_volumes[1].name = "USB_Drive"
        fake_volumes[2].name = "Backup_Disk"

        for fv in fake_volumes:
            fv.is_dir.return_value = True

        volumes_path = MagicMock(spec=Path)
        volumes_path.is_dir.return_value = True
        volumes_path.iterdir.return_value = iter(fake_volumes)
        mock_path_cls.return_value = volumes_path

        with patch("dlp.features.file_monitor.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"
            result = get_external_volumes()

        names = [v.name for v in result]
        assert "Macintosh HD" not in names
        assert "USB_Drive" in names
        assert "Backup_Disk" in names

    @patch("dlp.features.file_monitor.Path")
    def test_get_external_volumes_empty(self, mock_path_cls):
        from dlp.features.file_monitor import get_external_volumes

        # Only Macintosh HD present
        fake_volumes = [MagicMock(name="Macintosh HD", spec=Path)]
        fake_volumes[0].name = "Macintosh HD"
        fake_volumes[0].is_dir.return_value = True

        volumes_path = MagicMock(spec=Path)
        volumes_path.is_dir.return_value = True
        volumes_path.iterdir.return_value = iter(fake_volumes)
        mock_path_cls.return_value = volumes_path

        with patch("dlp.features.file_monitor.platform") as mock_platform:
            mock_platform.system.return_value = "Darwin"
            result = get_external_volumes()

        assert result == []


class TestCountRecentFiles:
    """Tests for counting recently-modified files."""

    @patch("dlp.features.file_monitor.Path")
    def test_count_recent_files_empty_dir(self, mock_path_cls):
        from dlp.features.file_monitor import count_recent_files

        mock_dir = MagicMock(spec=Path)
        mock_dir.rglob.return_value = iter([])
        mock_path_cls.return_value = mock_dir

        count = count_recent_files(mock_dir)
        assert count == 0


class TestCheckBulkCopy:
    """Tests for bulk-copy detection logic."""

    @patch("dlp.features.file_monitor.count_recent_files")
    def test_check_bulk_copy_under_threshold(self, mock_count):
        from dlp.features.file_monitor import check_bulk_copy

        fake_vol = MagicMock(spec=Path)
        fake_vol.name = "USB_Drive"
        mock_count.return_value = 10  # under threshold

        alerts = check_bulk_copy(volumes=[fake_vol], threshold=50)
        assert alerts == []

    @patch("dlp.features.file_monitor.count_recent_files")
    def test_check_bulk_copy_over_threshold(self, mock_count):
        from dlp.features.file_monitor import check_bulk_copy

        fake_vol = MagicMock(spec=Path)
        fake_vol.name = "USB_Drive"
        mock_count.return_value = 100  # over threshold

        alerts = check_bulk_copy(volumes=[fake_vol], threshold=50)
        assert len(alerts) >= 1

        alert = alerts[0]
        assert alert.file_count == 100
        assert alert.threshold == 50
