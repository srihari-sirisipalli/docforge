"""
DocForge — Batch Scheduler
=============================

Computes optimal batch configuration based on system capabilities:
  - Number of fast-path workers (CPU-bound)
  - Number of VLM workers (typically 1, GPU-bound)
  - Batch size for database operations
  - Memory budget for processing

Auto-tunes based on the SystemProfile from hardware detection.
"""

from __future__ import annotations

from dataclasses import dataclass

from docforge.infra.config import RuntimeConfig
from docforge.infra.hardware import SystemProfile
from docforge.infra.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BatchConfig:
    """Computed batch processing parameters.

    These values are auto-tuned from hardware + configuration, then
    used by the orchestrator to size worker pools.
    """
    fast_path_workers: int = 2
    """Number of parallel heuristic extraction workers."""

    vlm_workers: int = 1
    """Number of VLM workers (usually 1 — VLM uses all threads)."""

    batch_size: int = 100
    """Number of documents per database batch operation."""

    memory_limit_mb: int = 4096
    """Memory budget for processing (guards OOM)."""

    total_workers: int = 3
    """Total worker count (fast_path + vlm)."""


def compute_batch_config(
    config: RuntimeConfig,
    profile: SystemProfile,
    total_documents: int,
) -> BatchConfig:
    """Compute optimal batch parameters from config + hardware.

    The goal is to maximise throughput without exceeding memory limits
    or starving the VLM of CPU/GPU resources.

    Args:
        config:          Runtime configuration.
        profile:         System hardware profile.
        total_documents: Total number of documents to process.

    Returns:
        BatchConfig with auto-tuned parameters.
    """
    batch = BatchConfig()

    # ── VLM workers ──────────────────────────────────────────────────────
    # VLM is single-threaded from the scheduler's perspective (it uses
    # all available GPU/CPU threads internally).
    batch.vlm_workers = config.performance.vlm_concurrent

    # ── Fast-path workers ────────────────────────────────────────────────
    if config.performance.fast_path_workers > 0:
        batch.fast_path_workers = config.performance.fast_path_workers
    elif config.performance.max_workers > 0:
        batch.fast_path_workers = max(1, config.performance.max_workers - batch.vlm_workers)
    else:
        # Auto: use (cores - 1 - vlm_workers), minimum 1
        available_cores = max(1, profile.cpu_cores - 1)
        batch.fast_path_workers = max(1, available_cores - batch.vlm_workers)

    batch.total_workers = batch.fast_path_workers + batch.vlm_workers

    # ── Batch size ───────────────────────────────────────────────────────
    batch.batch_size = min(config.performance.batch_size, total_documents)

    # ── Memory limit ─────────────────────────────────────────────────────
    if config.performance.memory_limit_mb > 0:
        batch.memory_limit_mb = config.performance.memory_limit_mb
    else:
        # Auto: 70% of available RAM
        batch.memory_limit_mb = int(profile.available_ram_gb * 1024 * 0.7)

    logger.info(
        "Batch config: %d fast-path workers, %d VLM workers, "
        "batch_size=%d, memory_limit=%d MB",
        batch.fast_path_workers, batch.vlm_workers,
        batch.batch_size, batch.memory_limit_mb,
    )

    return batch
