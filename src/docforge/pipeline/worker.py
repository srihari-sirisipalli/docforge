"""
DocForge — Pipeline Workers
==============================

Two worker types for the two-track parallel architecture:

  1. fast_path_worker — Processes documents with good embedded text
     using heuristic extraction only. Multiple instances run in parallel.

  2. vlm_worker — Processes scanned/image documents using the VLM.
     Typically runs as a single instance (VLM uses all GPU/CPU threads).

Both workers:
  - Claim work from the database atomically (no double-processing)
  - Run the full extraction → merge → naming pipeline
  - Update the database with results or errors
  - Handle failures gracefully (mark as error, continue processing)
"""

from __future__ import annotations

import time
import traceback
from pathlib import Path

from docforge.extractors.heuristic import HeuristicExtractor
from docforge.extractors.merger import FieldMerger
from docforge.extractors.metadata import MetadataExtractor
from docforge.extractors.renderer import PageRenderer
from docforge.extractors.text import TextExtractor
from docforge.extractors.vlm_extractor import VLMExtractor
from docforge.infra.config import RuntimeConfig
from docforge.infra.logging import get_logger
from docforge.models.enums import DocumentStatus, ExtractionStrategy
from docforge.models.record import DocumentRecord
from docforge.naming.generator import FilenameGenerator
from docforge.ocr.engine import OCREngine
from docforge.organizer.tree_builder import FolderOrganizer
from docforge.pipeline.router import StrategyRouter
from docforge.storage.database import StateDB
from docforge.vlm.manager import ModelManager

logger = get_logger(__name__)


def process_single_document(
    record: DocumentRecord,
    config: RuntimeConfig,
    strategy: ExtractionStrategy,
    renderer: PageRenderer,
    model_manager: ModelManager | None,
    ocr_engine: OCREngine | None,
    organizer: FolderOrganizer | None,
) -> DocumentRecord:
    """Process a single document through all pipeline stages.

    This is the core processing function used by both fast-path and
    VLM workers. It runs stages 1-5 sequentially for one document.

    Args:
        record:         DocumentRecord with file_id and original_path set.
        config:         Runtime configuration.
        strategy:       Pre-determined extraction strategy.
        renderer:       Page renderer instance.
        model_manager:  VLM model manager (None if VLM disabled).
        ocr_engine:     OCR engine (None if OCR disabled).
        organizer:      Folder organizer (None if organisation disabled).

    Returns:
        The updated DocumentRecord.
    """
    start = time.perf_counter()
    path = record.original_path

    logger.info(
        "Processing: %s [%s] — %s",
        Path(path).name, record.file_id[:12], strategy.value,
    )

    try:
        # ── Stage 1: Metadata extraction ─────────────────────────────────
        metadata_extractor = MetadataExtractor()
        metadata_extractor.process(record)

        if record.error_message:
            record.status = DocumentStatus.ERROR
            return record

        # ── Stage 2: Text extraction + quality scoring ───────────────────
        text_extractor = TextExtractor(max_pages=config.extraction.max_pages_text)
        record.raw_text, record.text_quality_score = text_extractor.extract(path)

        # ── Stage 3: Extraction (strategy-dependent) ─────────────────────
        if strategy in (ExtractionStrategy.VLM_ONLY, ExtractionStrategy.VLM_PLUS_HEURISTIC):
            # Render pages for VLM
            page_images = renderer.render(path, record.file_id, purpose="vlm")

            if model_manager and model_manager.is_available() and page_images:
                vlm_extractor = VLMExtractor(model_manager)
                vlm_extractor.extract(page_images, record)

            # Also run heuristic if cross-validating or if VLM failed
            if strategy == ExtractionStrategy.VLM_PLUS_HEURISTIC or record.vlm_fields is None:
                heuristic = HeuristicExtractor()
                heuristic.process(record)

            # Clean up rendered images
            renderer.cleanup(record.file_id)

        elif strategy == ExtractionStrategy.OCR_HEURISTIC:
            # Render pages for OCR
            page_images = renderer.render(path, record.file_id, purpose="ocr")

            if ocr_engine and page_images:
                ocr_engine.process(page_images, record)

            # Run heuristic on OCR text
            heuristic = HeuristicExtractor()
            heuristic.process(record)

            renderer.cleanup(record.file_id)

        elif strategy == ExtractionStrategy.TEXT_HEURISTIC:
            # Fast path — heuristic only, no rendering needed
            heuristic = HeuristicExtractor()
            heuristic.process(record)

        else:
            # METADATA_ONLY — nothing more to do
            pass

        # ── Stage 4: Field merging ───────────────────────────────────────
        merger = FieldMerger()
        merger.process(record)

        # ── Stage 5: Filename generation ─────────────────────────────────
        # If VLM directly suggested a name, use it; otherwise use template
        if record.vlm_suggested_name:
            from docforge.naming.sanitizer import sanitise_filename
            record.canonical_name = record.vlm_suggested_name + ".pdf"
        else:
            name_gen = FilenameGenerator(config.naming)
            name_gen.process(record)

        # ── Stage 5b: Target directory (if organiser enabled) ────────────
        if organizer:
            record.target_directory = organizer.compute_target_dir(record.merged_fields)

        # ── Mark complete ────────────────────────────────────────────────
        record.status = DocumentStatus.COMPLETE
        record.processing_time_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "  Done: %s → '%s' [%d ms, %s]",
            Path(path).name, record.canonical_name,
            record.processing_time_ms, strategy.value,
        )

    except Exception as exc:
        record.status = DocumentStatus.ERROR
        record.error_message = f"Processing failed: {exc}"
        record.processing_time_ms = int((time.perf_counter() - start) * 1000)

        logger.error(
            "  FAILED: %s — %s [%d ms]",
            Path(path).name, exc, record.processing_time_ms,
        )
        logger.debug("  Traceback: %s", traceback.format_exc())

    return record


def fast_path_worker(
    worker_id: int,
    db: StateDB,
    config: RuntimeConfig,
    renderer: PageRenderer,
    organizer: FolderOrganizer | None,
    progress_callback=None,
) -> int:
    """Worker loop for fast-path (heuristic) document processing.

    Claims documents with good text quality from the database and
    processes them using heuristic extraction. Runs until no more
    fast-path documents are available.

    Args:
        worker_id:         Numeric worker identifier (for logging).
        db:                StateDB instance (thread-local connection).
        config:            Runtime configuration.
        renderer:          Page renderer instance.
        organizer:         Folder organizer (or None).
        progress_callback: Optional callable(file_id) for progress updates.

    Returns:
        Number of documents processed by this worker.
    """
    processed = 0
    logger.info("Fast-path worker %d starting", worker_id)

    while True:
        # Atomically claim next document
        claimed = db.claim_next_fast_path(worker_id)
        if claimed is None:
            break

        record = DocumentRecord(
            file_id=claimed["file_id"],
            original_path=claimed["original_path"],
        )

        record = process_single_document(
            record=record,
            config=config,
            strategy=ExtractionStrategy.TEXT_HEURISTIC,
            renderer=renderer,
            model_manager=None,
            ocr_engine=None,
            organizer=organizer,
        )

        # Save results to database
        db.update_record(
            record, stage=record.current_stage,
            status=record.status.value,
        )

        if progress_callback:
            progress_callback(record.file_id)

        processed += 1

    logger.info("Fast-path worker %d finished: %d documents", worker_id, processed)
    return processed


def vlm_worker(
    db: StateDB,
    config: RuntimeConfig,
    renderer: PageRenderer,
    model_manager: ModelManager,
    router: StrategyRouter,
    ocr_engine: OCREngine | None,
    organizer: FolderOrganizer | None,
    progress_callback=None,
) -> int:
    """Worker loop for VLM-path document processing.

    Claims documents with low text quality and processes them using
    the VLM. Falls back to OCR if VLM fails for a specific document.

    Args:
        db:                StateDB instance.
        config:            Runtime configuration.
        renderer:          Page renderer instance.
        model_manager:     VLM model manager.
        router:            Strategy router.
        ocr_engine:        OCR engine (fallback).
        organizer:         Folder organizer (or None).
        progress_callback: Optional callable(file_id) for progress updates.

    Returns:
        Number of documents processed.
    """
    processed = 0
    logger.info("VLM worker starting")

    while True:
        claimed = db.claim_next_vlm_needed()
        if claimed is None:
            break

        record = DocumentRecord(
            file_id=claimed["file_id"],
            original_path=claimed["original_path"],
        )

        # Run text extraction to get quality score for routing
        text_extractor = TextExtractor(max_pages=config.extraction.max_pages_text)
        record.raw_text, record.text_quality_score = text_extractor.extract(
            record.original_path
        )

        # Route to determine exact strategy
        strategy = router.route(record)

        record = process_single_document(
            record=record,
            config=config,
            strategy=strategy,
            renderer=renderer,
            model_manager=model_manager,
            ocr_engine=ocr_engine,
            organizer=organizer,
        )

        # Save results
        db.update_record(
            record, stage=record.current_stage,
            status=record.status.value,
        )

        if progress_callback:
            progress_callback(record.file_id)

        processed += 1

    logger.info("VLM worker finished: %d documents", processed)
    return processed
