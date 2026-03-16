"""
DocForge — Pipeline Stage Definitions
========================================

Defines the processing stages as a protocol/interface and provides
stage execution wrappers with timing, error handling, and state updates.

Pipeline Stages:
  1. MetadataExtractor  — Read PDF metadata (title, author, dates)
  2. TextExtractor      — Extract embedded text + score quality
  3. StrategyRouter     — Route to VLM, Heuristic, or OCR path
  4. FieldMerger        — Merge results from all sources
  5. FilenameGenerator  — Produce canonical filename + target path
"""

from __future__ import annotations

import time
import traceback
from typing import Protocol

from docforge.infra.logging import get_logger
from docforge.models.record import DocumentRecord

logger = get_logger(__name__)


class StageProcessor(Protocol):
    """Protocol for pipeline stage processors.

    Each stage reads from and writes to the DocumentRecord in-place.
    """
    def process(self, record: DocumentRecord) -> None: ...


def run_stage(
    stage_name: str,
    stage_num: int,
    processor: StageProcessor,
    record: DocumentRecord,
) -> bool:
    """Execute a pipeline stage with timing, logging, and error handling.

    Args:
        stage_name: Human-readable stage name (for logging).
        stage_num:  Stage number (1-5).
        processor:  The stage processor instance.
        record:     DocumentRecord to process.

    Returns:
        True if the stage completed successfully, False on error.
    """
    start = time.perf_counter()

    try:
        processor.process(record)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        record.current_stage = max(record.current_stage, stage_num)
        record.processing_time_ms += elapsed_ms

        logger.debug(
            "  [Stage %d: %s] completed in %d ms",
            stage_num, stage_name, elapsed_ms,
        )
        return True

    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error(
            "  [Stage %d: %s] FAILED after %d ms: %s",
            stage_num, stage_name, elapsed_ms, exc,
        )
        logger.debug("  Traceback: %s", traceback.format_exc())

        record.error_message = f"Stage {stage_num} ({stage_name}) failed: {exc}"
        return False
