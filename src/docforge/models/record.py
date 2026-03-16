"""
DocForge — Document Record and Operation Models
================================================

The DocumentRecord is the central data object that flows through the entire
pipeline. Each stage reads from it, processes, and writes back to it.

FileOp represents a single file operation (rename/move) in the transaction log.
PendingDocument is the lightweight record created during the scan phase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from docforge.models.enums import DocumentStatus, ExtractionStrategy
from docforge.models.fields import ExtractedFields, empty_fields


# =============================================================================
# PendingDocument — Created during scan phase
# =============================================================================

@dataclass
class PendingDocument:
    """Lightweight record created by the scanner for each discovered PDF.

    Contains only identity information needed to register the document
    in the state database. Full extraction happens later in the pipeline.
    """
    file_id: str
    """Unique identifier: SHA-256 of first 64KB concatenated with file size."""

    original_path: str
    """Absolute path to the PDF file on disk."""

    file_size_bytes: int
    """File size in bytes, used for deduplication and skip logic."""


# =============================================================================
# DocumentRecord — Main pipeline data object
# =============================================================================

@dataclass
class DocumentRecord:
    """Complete record for a single document flowing through the pipeline.

    Each pipeline stage reads from and writes to this record. The state
    database serialises and deserialises this object for persistence,
    checkpointing, and resume logic.

    Stages:
        1. MetadataExtractor  → fills pdf_metadata, metadata_fields, page_count
        2. PageRenderer       → fills rendered_pages, raw_text, text_quality_score
        3. StrategyRouter     → fills vlm_fields or heuristic_fields (or both)
        4. FieldMerger        → fills merged_fields
        5. NameGenerator      → fills canonical_name, target_directory
    """

    # ── Identity ────────────────────────────────────────────────────────────
    file_id: str = ""
    """SHA-256(first_64KB) + file_size — fast, collision-resistant identifier."""

    original_path: str = ""
    """Absolute path to the original PDF file."""

    file_size_bytes: int = 0
    """File size in bytes."""

    # ── Stage 1 output: PDF metadata ────────────────────────────────────────
    pdf_metadata: dict = field(default_factory=dict)
    """Raw PDF Info dictionary as returned by PyMuPDF."""

    metadata_fields: ExtractedFields = field(default_factory=empty_fields)
    """Fields extracted from the PDF Info/XMP metadata."""

    page_count: int = 0
    """Total number of pages in the PDF."""

    # ── Stage 2 output: Page rendering & text probe ─────────────────────────
    rendered_pages: list[str] = field(default_factory=list)
    """Paths to rendered PNG images (temporary files, cleaned up after use)."""

    raw_text: str = ""
    """Embedded text extracted from the first N pages (if available)."""

    text_quality_score: float = 0.0
    """Quality score for embedded text (0.0 = garbage/none, 1.0 = perfect).
    Used by the StrategyRouter to decide VLM vs. heuristic path."""

    # ── Stage 3 output: Extraction results ──────────────────────────────────
    extraction_strategy: str = ""
    """Which strategy was used: 'vlm_only', 'vlm_plus_heuristic', etc."""

    vlm_fields: Optional[ExtractedFields] = None
    """Fields extracted by the VLM vision pass (Path A)."""

    vlm_model_used: str = ""
    """Name of the VLM model used (e.g., 'minicpm-v')."""

    vlm_raw_response: str = ""
    """Raw JSON response from the VLM, stored for debugging."""

    vlm_suggested_name: str = ""
    """Filename directly suggested by the VLM."""

    heuristic_fields: Optional[ExtractedFields] = None
    """Fields extracted by text/OCR + heuristic rules (Paths B/C)."""

    ocr_text: str = ""
    """OCR-extracted text if Path C (OCR fallback) was used."""

    ocr_confidence: float = 0.0
    """Average OCR character confidence (0.0–1.0)."""

    # ── Stage 4 output: Merged result ───────────────────────────────────────
    merged_fields: ExtractedFields = field(default_factory=empty_fields)
    """Final reconciled fields from all extraction sources."""

    # ── Stage 5 output: Generated filename ──────────────────────────────────
    canonical_name: str = ""
    """The deterministic output filename (e.g., 'dnv_rules_steel_ships_2023.pdf')."""

    target_directory: str = ""
    """Target directory path if folder organisation is enabled."""

    # ── Processing state ────────────────────────────────────────────────────
    current_stage: int = 0
    """Last completed pipeline stage (0 = not started, 5 = complete)."""

    status: DocumentStatus = DocumentStatus.PENDING
    """Current processing status."""

    error_message: str = ""
    """Error message if status is ERROR."""

    processing_time_ms: int = 0
    """Total processing time in milliseconds."""

    last_updated: datetime = field(default_factory=datetime.now)
    """Timestamp of last state update."""


# =============================================================================
# FileOp — Single file operation for the transaction log
# =============================================================================

@dataclass
class FileOp:
    """A single file system operation recorded in the transaction log.

    All rename/move operations are logged before execution and can be
    rolled back in reverse order if something goes wrong.
    """
    op_id: int = 0
    """Auto-incremented operation ID."""

    job_id: str = ""
    """ID of the parent job."""

    file_id: str = ""
    """ID of the document being operated on."""

    operation: str = ""
    """Operation type: 'rename', 'move', 'mkdir'."""

    source_path: str = ""
    """Original file path before the operation."""

    target_path: str = ""
    """Target file path after the operation."""

    executed: int = 0
    """Execution state: 0 = pending, 1 = done, -1 = rolled back."""

    executed_at: Optional[str] = None
    """ISO timestamp of when the operation was executed."""

    checksum_before: str = ""
    """SHA-256 checksum of the file before the operation (integrity check)."""

    checksum_after: str = ""
    """SHA-256 checksum of the file after the operation (verification)."""
