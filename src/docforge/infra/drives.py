"""
DocForge — External Drive Support
===================================

Handles external/removable drives and network-mounted filesystems.
Provides drive classification, mount monitoring, and I/O strategy
adjustments for different storage types.

External drives are treated as potentially unreliable:
  - State is always stored locally (~/.docforge/state.db)
  - I/O parallelism is reduced for HDD and network mounts
  - Drive disconnection is monitored during processing
"""

from __future__ import annotations

import os
import platform
from enum import Enum
from pathlib import Path

import psutil

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class DriveType(str, Enum):
    """Classification of storage devices."""
    SSD = "ssd"
    HDD = "hdd"
    NETWORK = "network"
    REMOVABLE = "removable"
    UNKNOWN = "unknown"


class DriveManager:
    """Manages external and network drive detection and monitoring."""

    def classify_drive(self, path: str) -> DriveType:
        """Classify the storage type for a given path.

        Args:
            path: File or directory path to classify.

        Returns:
            DriveType indicating the storage medium.
        """
        path = str(Path(path).resolve())

        # Network paths (UNC on Windows, NFS/CIFS on Linux)
        if path.startswith("\\\\") or path.startswith("//"):
            return DriveType.NETWORK

        # Check mounted partitions
        try:
            partitions = psutil.disk_partitions(all=True)
            for part in partitions:
                if path.startswith(part.mountpoint):
                    # Network filesystem types
                    if part.fstype in ("nfs", "cifs", "smbfs", "nfs4", "fuse.sshfs"):
                        return DriveType.NETWORK

                    # Removable on Windows
                    if platform.system() == "Windows" and "removable" in part.opts.lower():
                        return DriveType.REMOVABLE

                    # On Linux, check for removable block devices
                    if platform.system() == "Linux" and "/media/" in part.mountpoint:
                        return DriveType.REMOVABLE

        except (PermissionError, OSError) as exc:
            logger.debug("Could not classify drive for %s: %s", path, exc)

        return DriveType.UNKNOWN

    def is_accessible(self, path: str) -> bool:
        """Check if a path is currently accessible (drive still mounted).

        Args:
            path: Path to check.

        Returns:
            True if the path exists and is readable.
        """
        try:
            return os.access(path, os.R_OK)
        except OSError:
            return False

    def get_free_space_gb(self, path: str) -> float:
        """Get free disk space at the given path in gigabytes.

        Args:
            path: Path to check.

        Returns:
            Free space in GB, or 0.0 if unavailable.
        """
        try:
            usage = psutil.disk_usage(path)
            return usage.free / (1024 ** 3)
        except (OSError, FileNotFoundError):
            return 0.0

    def recommended_workers(self, drive_type: DriveType, default: int) -> int:
        """Adjust worker count based on drive type.

        HDD and network drives get fewer parallel workers to avoid
        thrashing and excessive latency.

        Args:
            drive_type: Classified drive type.
            default:    Default worker count for SSD.

        Returns:
            Adjusted worker count.
        """
        adjustments = {
            DriveType.SSD: default,
            DriveType.HDD: min(default, 2),
            DriveType.NETWORK: min(default, 1),
            DriveType.REMOVABLE: min(default, 2),
            DriveType.UNKNOWN: default,
        }
        return adjustments.get(drive_type, default)
