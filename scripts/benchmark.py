#!/usr/bin/env python3
"""
DocForge Benchmark Script
============================

Measures processing throughput and per-stage timing.
Run after generating test PDFs with generate_test_pdfs.py.

Usage:
    python scripts/benchmark.py [--source ./test_pdfs] [--no-vlm]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from docforge.infra.config import load_config
from docforge.infra.hardware import profile_system
from docforge.infra.logging import setup_logging
from docforge.pipeline.orchestrator import PipelineOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Benchmark DocForge processing")
    parser.add_argument("--source", "-s", default="./test_pdfs",
                        help="Source directory with PDFs")
    parser.add_argument("--no-vlm", action="store_true",
                        help="Disable VLM (heuristic-only mode)")
    parser.add_argument("--workers", "-w", type=int, default=0,
                        help="Worker count (0=auto)")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"Source directory not found: {source}")
        print("Run: python scripts/generate_test_pdfs.py first")
        return

    setup_logging("INFO", "~/.docforge/logs/")
    config = load_config()
    config.vlm.enabled = not args.no_vlm
    if args.workers:
        config.performance.max_workers = args.workers
    config.safety.dry_run = True

    profile = profile_system(str(source))

    print(f"\n{'='*60}")
    print(f"DocForge Benchmark")
    print(f"{'='*60}")
    print(f"Source:  {source}")
    print(f"VLM:     {'enabled' if config.vlm.enabled else 'disabled'}")
    print(f"Workers: {config.performance.max_workers or 'auto'}")
    print(f"CPU:     {profile.cpu_cores} cores")
    print(f"RAM:     {profile.available_ram_gb:.1f} GB available")
    print(f"{'='*60}\n")

    start = time.perf_counter()
    orchestrator = PipelineOrchestrator(config, profile)
    stats = orchestrator.run(str(source))
    elapsed = time.perf_counter() - start

    total = stats.get("total", 0)
    complete = stats.get("complete", 0)

    print(f"\n{'='*60}")
    print(f"BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"Total documents:    {total}")
    print(f"Completed:          {complete}")
    print(f"Errors:             {stats.get('errors', 0)}")
    print(f"Total time:         {elapsed:.1f}s")

    if complete > 0:
        print(f"Throughput:         {complete / elapsed:.1f} docs/sec")
        print(f"Avg time/doc:       {stats.get('avg_processing_ms', 0):.0f} ms")
        print(f"Max time/doc:       {stats.get('max_processing_ms', 0):.0f} ms")

    print(f"\nStrategies:")
    for strategy, count in sorted(stats.get("strategies", {}).items()):
        print(f"  {strategy}: {count}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
