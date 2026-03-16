"""
DocForge — Pipeline Orchestrator
===================================

The top-level coordinator that runs the entire document processing pipeline:

  1. Scan directories for PDFs
  2. Register documents in the state database
  3. Profile system hardware and auto-configure
  4. Start VLM runtime (if enabled and capable)
  5. Run Stage 1-2 (metadata + text probe) on all documents
  6. Launch two-track parallel workers:
     - Fast-path workers for clean digital PDFs
     - VLM worker for scanned/image PDFs
  7. Generate filenames and target paths
  8. Print final statistics

The orchestrator is designed for resume: if interrupted, re-running
picks up where it left off (pending documents are not re-processed).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from docforge.extractors.metadata import MetadataExtractor
from docforge.extractors.renderer import PageRenderer
from docforge.extractors.text import TextExtractor
from docforge.infra.config import RuntimeConfig
from docforge.infra.hardware import SystemProfile, check_ollama_installed, check_tesseract_installed
from docforge.infra.logging import get_logger
from docforge.models.enums import DocumentStatus, ExtractionStrategy
from docforge.models.record import DocumentRecord
from docforge.naming.generator import FilenameGenerator
from docforge.ocr.engine import OCREngine
from docforge.organizer.tree_builder import FolderOrganizer
from docforge.pipeline.router import StrategyRouter
from docforge.pipeline.scheduler import BatchConfig, compute_batch_config
from docforge.pipeline.worker import process_single_document
from docforge.reporting.formatters import (
    console,
    create_progress,
    print_final_stats,
    print_processing_config,
    print_scan_summary,
    print_system_profile,
)
from docforge.scanner import DirectoryScanner
from docforge.storage.database import StateDB
from docforge.vlm.manager import ModelManager

logger = get_logger(__name__)


class PipelineOrchestrator:
    """Coordinates the end-to-end document processing pipeline.

    Usage:
        orchestrator = PipelineOrchestrator(config, profile)
        stats = orchestrator.run(source="/path/to/pdfs")
    """

    def __init__(self, config: RuntimeConfig, profile: SystemProfile):
        """
        Args:
            config:  Runtime configuration (from TOML + CLI overrides).
            profile: System hardware profile (from auto-detection).
        """
        self.config = config
        self.profile = profile
        self.db: StateDB | None = None
        self.model_manager: ModelManager | None = None
        self.ocr_engine: OCREngine | None = None
        self.organizer: FolderOrganizer | None = None
        self.renderer: PageRenderer | None = None

    def run(self, source: str) -> dict:
        """Execute the complete processing pipeline.

        Args:
            source: Path to the source directory (or single PDF).

        Returns:
            Final statistics dict with processing results.
        """
        total_start = time.perf_counter()

        # ── Initialise components ────────────────────────────────────────
        self.db = StateDB(self.config.general.db_path)
        self.renderer = PageRenderer(self.config)

        # Print system and config info
        print_system_profile(self.profile)
        print_processing_config(self.config, self.profile)

        # ── Phase 1: Scan ────────────────────────────────────────────────
        scanner = DirectoryScanner(self.config.scanner)
        pending = scanner.scan(source)

        if not pending:
            console.print("[yellow]No PDF files found in the source directory.[/yellow]")
            return {"total": 0, "complete": 0, "errors": 0}

        # Register in database
        inserted = self.db.insert_pending_documents(pending)
        total = self.db.get_total_count()
        print_scan_summary(total, source)

        # Create job record
        job_id = self.db.create_job(
            source_path=source,
            config_json=json.dumps({"vlm": self.config.vlm.model}),
        )

        # ── Phase 2: Setup extractors ────────────────────────────────────
        self._setup_vlm()
        self._setup_ocr()
        self._setup_organizer()

        # Compute batch configuration
        batch_config = compute_batch_config(self.config, self.profile, total)

        # ── Phase 3: Stage 1-2 pre-processing ────────────────────────────
        # Run metadata extraction and text probing for all pending docs
        console.print("\n[bold cyan]Phase 1/2:[/bold cyan] Metadata extraction & text probing...")
        self._run_preprocess(batch_config)

        # ── Phase 4: Two-track parallel processing ───────────────────────
        console.print("\n[bold cyan]Phase 2/2:[/bold cyan] Extraction & naming...")
        self._run_extraction(batch_config)

        # ── Phase 5: Cleanup & stats ─────────────────────────────────────
        if self.renderer:
            self.renderer.cleanup_all()

        if self.model_manager:
            self.model_manager.stop()

        # Final statistics
        self.db.complete_job(job_id)
        stats = self.db.get_final_stats()

        total_elapsed = time.perf_counter() - total_start
        stats["total_time_seconds"] = round(total_elapsed, 1)

        print_final_stats(stats)
        console.print(
            f"[dim]Total pipeline time: {total_elapsed:.1f}s "
            f"(Job ID: {job_id})[/dim]\n"
        )

        self.db.close()
        return stats

    # =====================================================================
    # Setup Helpers
    # =====================================================================

    def _setup_vlm(self) -> None:
        """Initialise the VLM runtime if enabled and hardware supports it."""
        if not self.config.vlm.enabled:
            console.print("[dim]VLM: disabled in configuration[/dim]")
            return

        if not self.profile.can_run_vlm:
            console.print(
                "[yellow]VLM: insufficient RAM "
                f"({self.profile.available_ram_gb:.1f} GB available). "
                "Falling back to heuristic/OCR.[/yellow]"
            )
            self.config.vlm.enabled = False
            return

        # Check runtime availability
        if self.config.vlm.runtime == "ollama" and not check_ollama_installed():
            console.print(
                "[yellow]VLM: Ollama not installed. "
                "Install from https://ollama.ai or disable VLM.[/yellow]"
            )
            self.config.vlm.enabled = False
            return

        try:
            self.model_manager = ModelManager(self.config.vlm)
            self.model_manager.start()
            console.print(
                f"[green]VLM ready:[/green] {self.config.vlm.model} "
                f"via {self.config.vlm.runtime}"
            )
        except RuntimeError as exc:
            console.print(f"[yellow]VLM startup failed: {exc}[/yellow]")
            console.print("[dim]Continuing with heuristic/OCR extraction only.[/dim]")
            self.model_manager = None
            self.config.vlm.enabled = False

    def _setup_ocr(self) -> None:
        """Initialise the OCR engine if available."""
        if not self.config.ocr.enabled:
            return

        self.ocr_engine = OCREngine(
            languages=self.config.ocr.languages,
            preprocess=self.config.ocr.preprocess,
        )

        if self.ocr_engine.is_available():
            console.print("[green]OCR ready:[/green] Tesseract")
        else:
            console.print("[dim]OCR: Tesseract not installed (optional fallback)[/dim]")

    def _setup_organizer(self) -> None:
        """Initialise the folder organizer if enabled."""
        if not self.config.organizer.enabled:
            return

        self.organizer = FolderOrganizer(
            strategy=self.config.organizer.strategy,
            base_dir=self.config.organizer.base_dir,
        )
        console.print(
            f"[dim]Organizer: {self.config.organizer.strategy} "
            f"→ {self.config.organizer.base_dir}[/dim]"
        )

    # =====================================================================
    # Processing Phases
    # =====================================================================

    def _run_preprocess(self, batch_config: BatchConfig) -> None:
        """Run Stage 1-2 (metadata + text probe) on all pending documents.

        This is done sequentially before the main extraction loop so
        that the router has text quality scores for all documents.
        """
        pending = self.db.get_all_pending()

        if not pending:
            console.print("[dim]No pending documents to preprocess.[/dim]")
            return

        metadata_extractor = MetadataExtractor()
        text_extractor = TextExtractor(
            max_pages=self.config.extraction.max_pages_text,
        )

        progress = create_progress()
        with progress:
            task = progress.add_task("Pre-processing", total=len(pending))

            for file_id, original_path in pending:
                try:
                    # Stage 1: Metadata
                    record = DocumentRecord(
                        file_id=file_id,
                        original_path=original_path,
                    )
                    metadata_extractor.process(record)

                    # Stage 2: Text probe
                    text, quality = text_extractor.extract(original_path)
                    self.db.update_text_probe(file_id, text, quality)

                    # Save Stage 1 results
                    self.db.update_record(record, stage=2, status="pending")

                except Exception as exc:
                    logger.warning(
                        "Preprocess failed for %s: %s", file_id[:12], exc,
                    )
                    self.db.mark_error(file_id, f"Preprocess failed: {exc}")

                progress.advance(task)

    def _run_extraction(self, batch_config: BatchConfig) -> None:
        """Run sequential extraction on all pending documents.

        If VLM is available, uses it to generate filenames for ALL documents.
        Otherwise falls back to heuristic naming.
        """
        vlm_available = (
            self.model_manager is not None
            and self.model_manager.is_available()
        )
        ocr_available = (
            self.ocr_engine is not None
            and self.ocr_engine.is_available()
        )

        router = StrategyRouter(
            vlm_available=vlm_available,
            ocr_available=ocr_available,
            vlm_enabled=self.config.vlm.enabled,
        )

        # Gather ALL pending documents
        all_docs = []
        while True:
            claimed = self.db.claim_next_fast_path(worker_id=0)
            if claimed is None:
                break
            all_docs.append(claimed)
        while True:
            claimed = self.db.claim_next_vlm_needed()
            if claimed is None:
                break
            all_docs.append(claimed)

        if not all_docs:
            console.print("[dim]No documents remaining for extraction.[/dim]")
            return

        progress = create_progress()
        processed = 0

        # VLM filename generator (if available)
        vlm_extractor = None
        if vlm_available and self.model_manager:
            from docforge.extractors.vlm_extractor import VLMExtractor
            vlm_extractor = VLMExtractor(self.model_manager)

        with progress:
            task = progress.add_task("Processing", total=len(all_docs))

            for claimed in all_docs:
                record = DocumentRecord(
                    file_id=claimed["file_id"],
                    original_path=claimed["original_path"],
                )

                # ── VLM filename generation for ALL documents ─────────
                if vlm_extractor and self.renderer:
                    page_images = self.renderer.render(
                        record.original_path, record.file_id, purpose="vlm",
                    )
                    if page_images:
                        suggested = vlm_extractor.generate_filename(page_images, record)
                        if suggested:
                            record.vlm_suggested_name = suggested
                        self.renderer.cleanup(record.file_id)

                # ── Run heuristic extraction (for metadata/fallback) ──
                record = process_single_document(
                    record=record,
                    config=self.config,
                    strategy=ExtractionStrategy.TEXT_HEURISTIC,
                    renderer=self.renderer,
                    model_manager=None,
                    ocr_engine=None,
                    organizer=self.organizer,
                )

                self.db.update_record(
                    record, stage=record.current_stage,
                    status=record.status.value,
                )
                processed += 1
                progress.update(task, completed=processed)

        # Handle any fallback-queued documents
        self._run_fallback_queue(router)

    def _run_fallback_queue(self, router: StrategyRouter) -> None:
        """Process documents that failed VLM and need OCR fallback."""
        fallback = self.db.get_fallback_queue()

        if not fallback:
            return

        console.print(
            f"\n[yellow]Processing {len(fallback)} fallback documents (OCR)...[/yellow]"
        )

        from docforge.pipeline.worker import process_single_document

        for doc in fallback:
            record = DocumentRecord(
                file_id=doc["file_id"],
                original_path=doc["original_path"],
            )

            record = process_single_document(
                record=record,
                config=self.config,
                strategy=router.route(record),
                renderer=self.renderer,
                model_manager=None,
                ocr_engine=self.ocr_engine,
                organizer=self.organizer,
            )

            self.db.update_record(
                record, stage=record.current_stage,
                status=record.status.value,
            )
