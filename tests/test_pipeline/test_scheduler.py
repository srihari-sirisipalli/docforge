"""Tests for the batch scheduler."""

from docforge.infra.config import RuntimeConfig
from docforge.infra.hardware import SystemProfile
from docforge.pipeline.scheduler import compute_batch_config


class TestBatchScheduler:
    """Test auto-tuning of batch parameters."""

    def test_default_config(self):
        config = RuntimeConfig()
        profile = SystemProfile(cpu_cores=8, available_ram_gb=16.0)

        batch = compute_batch_config(config, profile, total_documents=100)

        assert batch.fast_path_workers >= 1
        assert batch.vlm_workers >= 1
        assert batch.total_workers == batch.fast_path_workers + batch.vlm_workers
        assert batch.memory_limit_mb > 0

    def test_explicit_workers(self):
        config = RuntimeConfig()
        config.performance.max_workers = 4

        profile = SystemProfile(cpu_cores=8)
        batch = compute_batch_config(config, profile, total_documents=50)

        assert batch.fast_path_workers == 3  # 4 - 1 vlm worker

    def test_low_ram_system(self):
        config = RuntimeConfig()
        profile = SystemProfile(cpu_cores=2, available_ram_gb=2.0)

        batch = compute_batch_config(config, profile, total_documents=10)

        assert batch.fast_path_workers >= 1
        assert batch.memory_limit_mb < 2048

    def test_batch_size_capped(self):
        config = RuntimeConfig()
        config.performance.batch_size = 500
        profile = SystemProfile(cpu_cores=4)

        batch = compute_batch_config(config, profile, total_documents=50)

        assert batch.batch_size == 50  # Capped at total docs
