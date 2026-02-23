"""File activity monitoring on external / removable volumes."""

from __future__ import annotations

import logging
import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileActivityAlert:
    """Alert raised when recent file activity on a volume exceeds a threshold."""

    volume_path: str
    file_count: int
    threshold: int


def get_external_volumes() -> list[Path]:
    """Return a list of mounted external / removable volume paths.

    * **macOS** — entries in ``/Volumes`` excluding *Macintosh HD*.
    * **Windows** — removable drives (drive type 2) via ``GetLogicalDrives``.
    * **Linux** — directories under ``/media/$USER``.

    Returns an empty list on unsupported platforms or on error.
    """
    system = platform.system()

    try:
        if system == "Darwin":
            volumes_root = Path("/Volumes")
            if not volumes_root.is_dir():
                return []
            return [
                p
                for p in volumes_root.iterdir()
                if p.is_dir() and p.name != "Macintosh HD"
            ]

        if system == "Windows":
            import ctypes

            bitmask = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
            drives: list[Path] = []
            for letter_idx in range(26):
                if bitmask & (1 << letter_idx):
                    drive_letter = f"{chr(65 + letter_idx)}:\\"
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_letter)  # type: ignore[attr-defined]
                    if drive_type == 2:  # DRIVE_REMOVABLE
                        drives.append(Path(drive_letter))
            return drives

        if system == "Linux":
            user = os.environ.get("USER", "")
            if not user:
                return []
            media_path = Path(f"/media/{user}")
            if not media_path.is_dir():
                return []
            return [p for p in media_path.iterdir() if p.is_dir()]

    except Exception:
        logger.debug("Failed to enumerate external volumes", exc_info=True)

    return []


def count_recent_files(volume: Path, seconds: int = 60) -> int:
    """Count files on *volume* modified within the last *seconds*.

    Walks the volume recursively but caps iteration at 1000 files to
    avoid excessive I/O on large volumes.  Permission and OS errors on
    individual entries are silently skipped.
    """
    cutoff = time.time() - seconds
    count = 0
    seen = 0

    try:
        for entry in volume.rglob("*"):
            seen += 1
            if seen > 1000:
                break

            try:
                if entry.is_file() and entry.stat().st_mtime >= cutoff:
                    count += 1
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        logger.debug("Permission error scanning %s", volume, exc_info=True)

    return count


def check_bulk_copy(
    volumes: list[Path],
    threshold: int = 50,
    window_seconds: int = 60,
) -> list[FileActivityAlert]:
    """Check each volume for bulk file copy activity.

    Returns a :class:`FileActivityAlert` for every volume where the
    number of recently modified files meets or exceeds *threshold*.
    """
    alerts: list[FileActivityAlert] = []

    for volume in volumes:
        recent = count_recent_files(volume, seconds=window_seconds)

        if recent >= threshold:
            alert = FileActivityAlert(
                volume_path=str(volume),
                file_count=recent,
                threshold=threshold,
            )
            alerts.append(alert)
            logger.warning(
                "Bulk copy alert: %s has %d recently modified files (threshold %d)",
                volume,
                recent,
                threshold,
            )

    return alerts
