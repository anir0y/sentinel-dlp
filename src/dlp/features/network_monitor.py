"""Network exfiltration detection using psutil."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NetworkSnapshot:
    """Point-in-time network I/O counters for a single interface."""

    timestamp: float
    bytes_sent: int
    bytes_recv: int


@dataclass(frozen=True)
class TransferAlert:
    """Alert raised when an interface exceeds the transfer threshold."""

    interface: str
    mb_sent: float
    duration_seconds: float
    threshold_mb: float


class NetworkMonitor:
    """Monitors per-interface network I/O and alerts on large transfers."""

    def __init__(self, threshold_mb: float = 100.0) -> None:
        self.threshold_mb = threshold_mb
        self._last_snapshot: dict[str, NetworkSnapshot] | None = None

    def check(self) -> list[TransferAlert]:
        """Compare current network counters to the previous snapshot.

        On the first call, records a baseline and returns an empty list.
        Subsequent calls return alerts for any interface whose outbound
        transfer since the last check exceeds *threshold_mb*.
        """
        now = time.time()
        try:
            counters = psutil.net_io_counters(pernic=True)
        except Exception:
            logger.debug("Failed to read network I/O counters", exc_info=True)
            return []

        current: dict[str, NetworkSnapshot] = {
            iface: NetworkSnapshot(
                timestamp=now,
                bytes_sent=stats.bytes_sent,
                bytes_recv=stats.bytes_recv,
            )
            for iface, stats in counters.items()
        }

        if self._last_snapshot is None:
            self._last_snapshot = current
            logger.debug("Network monitor baseline recorded (%d interfaces)", len(current))
            return []

        alerts: list[TransferAlert] = []
        for iface, snap in current.items():
            prev = self._last_snapshot.get(iface)
            if prev is None:
                continue

            delta_bytes = snap.bytes_sent - prev.bytes_sent
            delta_mb = delta_bytes / (1024 * 1024)
            duration = snap.timestamp - prev.timestamp

            if delta_mb >= self.threshold_mb:
                alert = TransferAlert(
                    interface=iface,
                    mb_sent=round(delta_mb, 2),
                    duration_seconds=round(duration, 2),
                    threshold_mb=self.threshold_mb,
                )
                alerts.append(alert)
                logger.warning(
                    "Network exfiltration alert: %s sent %.2f MB in %.1fs",
                    iface,
                    delta_mb,
                    duration,
                )

        self._last_snapshot = current
        return alerts
