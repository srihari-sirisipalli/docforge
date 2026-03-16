"""
DocForge — Memory Management
==============================

Provides a MemoryGuard that monitors process memory usage and pauses
processing when the memory budget is exceeded. Prevents OOM crashes
during large batch processing runs.

Usage:
    guard = MemoryGuard(limit_mb=6000)
    if not guard.check():
        guard.wait_for_memory(timeout=60)
"""

from __future__ import annotations

import gc
import time

import psutil

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class MemoryGuard:
    """Monitors process memory usage and enforces a configurable budget.

    The pipeline checks the guard before processing each document batch.
    If memory exceeds the limit, processing pauses until GC frees enough
    memory or the timeout expires.
    """

    def __init__(self, limit_mb: int = 0):
        """Initialise with a memory limit.

        Args:
            limit_mb: Maximum RSS memory in megabytes. 0 = auto (70% of available).
        """
        if limit_mb <= 0:
            available = psutil.virtual_memory().available / (1024 * 1024)
            self.limit_bytes = int(available * 0.7) * 1024 * 1024
            logger.debug(
                "MemoryGuard: auto limit = %d MB (70%% of %.0f MB available)",
                self.limit_bytes // (1024 * 1024),
                available,
            )
        else:
            self.limit_bytes = limit_mb * 1024 * 1024
            logger.debug("MemoryGuard: manual limit = %d MB", limit_mb)

    def check(self) -> bool:
        """Return True if current memory usage is within the budget."""
        current = psutil.Process().memory_info().rss
        return current < self.limit_bytes

    def current_usage_mb(self) -> float:
        """Return current process RSS memory usage in megabytes."""
        return psutil.Process().memory_info().rss / (1024 * 1024)

    def wait_for_memory(self, timeout: float = 60.0) -> bool:
        """Block until memory drops below the limit or timeout expires.

        Triggers garbage collection on each check to encourage memory release.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True if memory dropped below limit, False if timeout expired.
        """
        start = time.time()
        while not self.check():
            elapsed = time.time() - start
            if elapsed > timeout:
                logger.warning(
                    "MemoryGuard: timeout after %.0fs — current=%.0f MB, limit=%.0f MB",
                    elapsed,
                    self.current_usage_mb(),
                    self.limit_bytes / (1024 * 1024),
                )
                return False
            gc.collect()
            time.sleep(1.0)
        return True
