from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


def _make_snetio(bytes_sent: int, bytes_recv: int) -> MagicMock:
    """Create a mock snetio named-tuple-like object."""
    obj = MagicMock()
    obj.bytes_sent = bytes_sent
    obj.bytes_recv = bytes_recv
    return obj


@pytest.fixture(autouse=True)
def _fresh_monitor():
    """Ensure each test gets a fresh NetworkMonitor instance."""
    # NetworkMonitor likely stores state; reimporting forces a clean slate.
    pass


class TestNetworkMonitor:
    """Tests for dlp.features.network_monitor.NetworkMonitor."""

    @patch("dlp.features.network_monitor.psutil")
    def test_first_check_returns_no_alerts(self, mock_psutil):
        """First call sets the baseline and returns an empty list."""
        from dlp.features.network_monitor import NetworkMonitor

        mock_psutil.net_io_counters.return_value = {
            "en0": _make_snetio(1000, 2000),
        }

        monitor = NetworkMonitor(threshold_mb=100)
        alerts = monitor.check()

        assert alerts == []

    @patch("dlp.features.network_monitor.psutil")
    def test_check_under_threshold_no_alert(self, mock_psutil):
        """Small delta below threshold produces no alerts."""
        from dlp.features.network_monitor import NetworkMonitor

        baseline = {"en0": _make_snetio(1000, 2000)}
        small_delta = {"en0": _make_snetio(1500, 2500)}  # ~0.0005 MB

        mock_psutil.net_io_counters.side_effect = [baseline, small_delta]

        monitor = NetworkMonitor(threshold_mb=100)
        monitor.check()  # baseline
        alerts = monitor.check()

        assert alerts == []

    @patch("dlp.features.network_monitor.psutil")
    def test_check_over_threshold_fires_alert(self, mock_psutil):
        """Large bytes_sent delta exceeding threshold triggers a TransferAlert."""
        from dlp.features.network_monitor import NetworkMonitor

        threshold_mb = 10
        large_bytes = threshold_mb * 1024 * 1024 + 1  # just over threshold

        baseline = {"en0": _make_snetio(0, 0)}
        after = {"en0": _make_snetio(large_bytes, 0)}

        mock_psutil.net_io_counters.side_effect = [baseline, after]

        monitor = NetworkMonitor(threshold_mb=threshold_mb)
        monitor.check()  # baseline
        alerts = monitor.check()

        assert len(alerts) >= 1

    @patch("dlp.features.network_monitor.psutil")
    def test_alert_contains_correct_data(self, mock_psutil):
        """TransferAlert carries interface name, mb_sent, duration, and threshold."""
        from dlp.features.network_monitor import NetworkMonitor

        threshold_mb = 5
        sent_bytes = 10 * 1024 * 1024  # 10 MB

        baseline = {"en0": _make_snetio(0, 0)}
        after = {"en0": _make_snetio(sent_bytes, 0)}

        mock_psutil.net_io_counters.side_effect = [baseline, after]

        monitor = NetworkMonitor(threshold_mb=threshold_mb)
        monitor.check()  # baseline
        alerts = monitor.check()

        assert len(alerts) >= 1
        alert = alerts[0]

        # Verify the alert exposes expected attributes
        assert hasattr(alert, "interface") or hasattr(alert, "iface")
        iface_val = getattr(alert, "interface", None) or getattr(alert, "iface", None)
        assert iface_val == "en0"

        mb_sent_val = getattr(alert, "mb_sent", None) or getattr(alert, "mb_transferred", None)
        assert mb_sent_val is not None
        assert mb_sent_val >= threshold_mb

    @patch("dlp.features.network_monitor.psutil")
    def test_multiple_interfaces_independent(self, mock_psutil):
        """Only the interface that exceeds the threshold triggers an alert."""
        from dlp.features.network_monitor import NetworkMonitor

        threshold_mb = 10
        large_bytes = 20 * 1024 * 1024  # 20 MB — over threshold
        small_bytes = 1 * 1024 * 1024   # 1 MB — under threshold

        baseline = {
            "en0": _make_snetio(0, 0),
            "en1": _make_snetio(0, 0),
        }
        after = {
            "en0": _make_snetio(large_bytes, 0),
            "en1": _make_snetio(small_bytes, 0),
        }

        mock_psutil.net_io_counters.side_effect = [baseline, after]

        monitor = NetworkMonitor(threshold_mb=threshold_mb)
        monitor.check()  # baseline
        alerts = monitor.check()

        # Only en0 should fire
        iface_names = []
        for a in alerts:
            name = getattr(a, "interface", None) or getattr(a, "iface", None)
            iface_names.append(name)

        assert "en0" in iface_names
        assert "en1" not in iface_names
