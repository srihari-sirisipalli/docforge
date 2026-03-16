"""
DocForge — State Database
==========================

Full CRUD interface to the SQLite state database. All pipeline state —
document records, job metadata, and processing metrics — flows through
this class.

Thread safety: Each thread should create its own StateDB instance
(which opens a separate connection). SQLite WAL mode supports concurrent
readers with one writer.

Usage:
    db = StateDB("~/.docforge/state.db")
    db.insert_pending_documents([PendingDocument(...), ...])
    record = db.claim_next_fast_path(worker_id=1)
"""

from __future__ import annotations

import json
import sqlite3
import zlib
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from docforge.infra.logging import get_logger
from docforge.models.enums import DocumentStatus
from docforge.models.record import DocumentRecord, PendingDocument
from docforge.storage.schema import configure_db, init_schema

logger = get_logger(__name__)


class StateDB:
    """Interface to the DocForge SQLite state database.

    Manages document records, job tracking, and processing metrics.
    Provides claim-based work distribution for parallel processing.
    """

    def __init__(self, db_path: str):
        """Open (or create) the state database.

        Args:
            db_path: Path to the SQLite file. Parent directories are created.
        """
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = configure_db(self.db_path)
        init_schema(self.conn)

        logger.debug("StateDB ready: %s", self.db_path)

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    # =====================================================================
    # Document CRUD
    # =====================================================================

    def insert_pending_documents(self, docs: list[PendingDocument]) -> int:
        """Batch-insert newly discovered documents as 'pending'.

        Duplicates (same file_id) are silently skipped via INSERT OR IGNORE.

        Args:
            docs: List of PendingDocument from the scanner.

        Returns:
            Number of documents actually inserted (excludes duplicates).
        """
        inserted = 0
        with self.conn:
            for doc in docs:
                try:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO documents (file_id, original_path, file_size) "
                        "VALUES (?, ?, ?)",
                        (doc.file_id, doc.original_path, doc.file_size_bytes),
                    )
                    inserted += self.conn.total_changes  # Will be 0 for duplicates
                except sqlite3.Error as exc:
                    logger.warning("Failed to insert %s: %s", doc.file_id[:12], exc)

        logger.info("Inserted %d new documents (of %d scanned)", inserted, len(docs))
        return inserted

    def update_text_probe(self, file_id: str, text: str, quality: float) -> None:
        """Store the text probe results from Stage 2.

        Args:
            file_id:  Document identifier.
            text:     Extracted embedded text (compressed for storage).
            quality:  Text quality score (0.0–1.0).
        """
        compressed = zlib.compress(text.encode("utf-8")) if text else b""
        with self.conn:
            self.conn.execute(
                "UPDATE documents SET text_quality = ?, raw_text = ?, "
                "current_stage = MAX(current_stage, 2), updated_at = datetime('now') "
                "WHERE file_id = ?",
                (quality, compressed, file_id),
            )

    def update_record(self, record: DocumentRecord, stage: int, status: str) -> None:
        """Update a document record after a pipeline stage completes.

        Serialises ExtractedFields as JSON for storage.

        Args:
            record: The updated DocumentRecord.
            stage:  Pipeline stage number (1–5).
            status: New status string ('processing', 'complete', 'error').
        """
        with self.conn:
            self.conn.execute(
                """UPDATE documents SET
                    current_stage = ?, status = ?,
                    pdf_metadata = ?, metadata_fields = ?,
                    extraction_strategy = ?,
                    vlm_fields = ?, vlm_model = ?, vlm_raw_response = ?,
                    heuristic_fields = ?,
                    merged_fields = ?,
                    canonical_name = ?, target_dir = ?,
                    processing_ms = ?, error_message = ?,
                    page_count = ?,
                    updated_at = datetime('now')
                WHERE file_id = ?""",
                (
                    stage, status,
                    json.dumps(record.pdf_metadata),
                    _serialise_fields(record.metadata_fields),
                    record.extraction_strategy,
                    _serialise_fields(record.vlm_fields),
                    record.vlm_model_used,
                    record.vlm_raw_response,
                    _serialise_fields(record.heuristic_fields),
                    _serialise_fields(record.merged_fields),
                    record.canonical_name,
                    record.target_directory,
                    record.processing_time_ms,
                    record.error_message,
                    record.page_count,
                    record.file_id,
                ),
            )

    def mark_error(self, file_id: str, error_msg: str) -> None:
        """Mark a document as errored with a message."""
        with self.conn:
            self.conn.execute(
                "UPDATE documents SET status = 'error', error_message = ?, "
                "updated_at = datetime('now') WHERE file_id = ?",
                (error_msg, file_id),
            )

    def requeue_for_fallback(self, file_id: str) -> None:
        """Re-queue a VLM-failed document for heuristic/OCR fallback."""
        with self.conn:
            self.conn.execute(
                "UPDATE documents SET status = 'pending', current_stage = 2, "
                "extraction_strategy = 'fallback_pending', "
                "updated_at = datetime('now') WHERE file_id = ?",
                (file_id,),
            )

    # =====================================================================
    # Work Distribution (claim-based)
    # =====================================================================

    def claim_next_fast_path(self, worker_id: int) -> Optional[dict]:
        """Claim the next document suitable for fast-path (heuristic) processing.

        Selects documents with text_quality >= 0.3 that are still pending.
        Atomically marks the document as 'processing' to prevent double-work.

        Args:
            worker_id: Numeric ID of the claiming worker (for logging).

        Returns:
            A dict with file_id and original_path, or None if no work remains.
        """
        with self.conn:
            row = self.conn.execute(
                "SELECT file_id, original_path FROM documents "
                "WHERE status = 'pending' AND text_quality >= 0.3 "
                "ORDER BY text_quality DESC LIMIT 1",
            ).fetchone()

            if row is None:
                return None

            self.conn.execute(
                "UPDATE documents SET status = 'processing', "
                "updated_at = datetime('now') WHERE file_id = ?",
                (row["file_id"],),
            )

        logger.debug("Worker %d claimed fast-path: %s", worker_id, row["file_id"][:12])
        return dict(row)

    def claim_next_vlm_needed(self) -> Optional[dict]:
        """Claim the next document needing VLM processing.

        Selects documents with text_quality < 0.3 (scanned/image PDFs)
        or those queued for VLM_PLUS_HEURISTIC cross-validation.

        Returns:
            A dict with file_id and original_path, or None if no work remains.
        """
        with self.conn:
            row = self.conn.execute(
                "SELECT file_id, original_path FROM documents "
                "WHERE status = 'pending' AND text_quality < 0.3 "
                "ORDER BY file_size ASC LIMIT 1",
            ).fetchone()

            if row is None:
                return None

            self.conn.execute(
                "UPDATE documents SET status = 'processing', "
                "updated_at = datetime('now') WHERE file_id = ?",
                (row["file_id"],),
            )

        logger.debug("VLM worker claimed: %s", row["file_id"][:12])
        return dict(row)

    def get_fallback_queue(self) -> list[dict]:
        """Get all documents that need fallback processing after VLM failure."""
        rows = self.conn.execute(
            "SELECT file_id, original_path FROM documents "
            "WHERE extraction_strategy = 'fallback_pending' AND status = 'pending'"
        ).fetchall()
        return [dict(r) for r in rows]

    # =====================================================================
    # Query Methods
    # =====================================================================

    def get_all_pending(self) -> list[tuple[str, str]]:
        """Get all pending documents as (file_id, original_path) tuples."""
        rows = self.conn.execute(
            "SELECT file_id, original_path FROM documents WHERE status = 'pending'"
        ).fetchall()
        return [(r["file_id"], r["original_path"]) for r in rows]

    def get_completed_records(self) -> list[dict]:
        """Get all completed document records for export/reporting."""
        rows = self.conn.execute(
            "SELECT * FROM documents WHERE status = 'complete' ORDER BY canonical_name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_records(self) -> list[dict]:
        """Get all document records regardless of status."""
        rows = self.conn.execute(
            "SELECT * FROM documents ORDER BY original_path"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_record(self, file_id: str) -> Optional[dict]:
        """Get a single document record by file_id."""
        row = self.conn.execute(
            "SELECT * FROM documents WHERE file_id = ?", (file_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_progress_stats(self) -> dict:
        """Get current processing progress for display.

        Returns:
            Dict with counts: total, pending, processing, complete, error, skipped.
        """
        row = self.conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as complete,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
            FROM documents
        """).fetchone()
        return dict(row)

    def get_final_stats(self) -> dict:
        """Get comprehensive final statistics for a completed job.

        Returns:
            Dict with counts, strategy breakdown, timing, and error summary.
        """
        stats = self.get_progress_stats()

        # Strategy breakdown
        strategy_rows = self.conn.execute(
            "SELECT extraction_strategy, COUNT(*) as cnt "
            "FROM documents WHERE status = 'complete' "
            "GROUP BY extraction_strategy"
        ).fetchall()
        stats["strategies"] = {r["extraction_strategy"]: r["cnt"] for r in strategy_rows}

        # Average processing time
        row = self.conn.execute(
            "SELECT AVG(processing_ms) as avg_ms, MAX(processing_ms) as max_ms "
            "FROM documents WHERE status = 'complete'"
        ).fetchone()
        stats["avg_processing_ms"] = row["avg_ms"] or 0
        stats["max_processing_ms"] = row["max_ms"] or 0

        return stats

    def get_total_count(self) -> int:
        """Get total number of documents in the database."""
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row["cnt"]

    # =====================================================================
    # Job Management
    # =====================================================================

    def create_job(self, source_path: str, config_json: str = "{}") -> str:
        """Create a new processing job and return its ID.

        Args:
            source_path: Root directory being processed.
            config_json: Serialised configuration for reproducibility.

        Returns:
            The generated job_id (UUID hex).
        """
        job_id = uuid4().hex[:12]
        total = self.get_total_count()

        with self.conn:
            self.conn.execute(
                "INSERT INTO jobs (job_id, source_path, config_json, total_files) "
                "VALUES (?, ?, ?, ?)",
                (job_id, source_path, config_json, total),
            )

        logger.info("Created job %s — %d documents from %s", job_id, total, source_path)
        return job_id

    def complete_job(self, job_id: str) -> None:
        """Mark a job as completed with final counts."""
        stats = self.get_progress_stats()
        with self.conn:
            self.conn.execute(
                "UPDATE jobs SET status = 'complete', completed_at = datetime('now'), "
                "processed_files = ?, error_count = ? WHERE job_id = ?",
                (stats["complete"], stats["errors"], job_id),
            )

    # =====================================================================
    # Operations Log (for rollback)
    # =====================================================================

    def log_operation(self, job_id: str, op: dict) -> int:
        """Log a file operation for rollback tracking.

        Args:
            job_id: Parent job ID.
            op:     Dict with keys: file_id, operation, source_path, target_path.

        Returns:
            The auto-generated operation ID.
        """
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO operations (job_id, file_id, operation, source_path, target_path) "
                "VALUES (?, ?, ?, ?, ?)",
                (job_id, op["file_id"], op["operation"],
                 op["source_path"], op["target_path"]),
            )
        return cursor.lastrowid

    def mark_operation_executed(self, op_id: int) -> None:
        """Mark an operation as successfully executed."""
        with self.conn:
            self.conn.execute(
                "UPDATE operations SET executed = 1, executed_at = datetime('now') "
                "WHERE op_id = ?",
                (op_id,),
            )

    def mark_operation_rolled_back(self, op_id: int) -> None:
        """Mark an operation as rolled back."""
        with self.conn:
            self.conn.execute(
                "UPDATE operations SET executed = -1 WHERE op_id = ?",
                (op_id,),
            )

    def get_executed_operations(self, job_id: str, order: str = "ASC") -> list[dict]:
        """Get all executed operations for a job, ordered for rollback.

        Args:
            job_id: The job to query.
            order:  "ASC" for execution order, "DESC" for rollback order.

        Returns:
            List of operation dicts.
        """
        rows = self.conn.execute(
            f"SELECT * FROM operations WHERE job_id = ? AND executed = 1 "
            f"ORDER BY op_id {order}",
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_job_id(self) -> Optional[str]:
        """Get the most recent job ID."""
        row = self.conn.execute(
            "SELECT job_id FROM jobs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row["job_id"] if row else None

    # =====================================================================
    # Metrics
    # =====================================================================

    def log_metric(self, file_id: str, stage: int,
                   duration_ms: int, memory_mb: float, method: str) -> None:
        """Log a performance metric for a pipeline stage."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO metrics (file_id, stage, duration_ms, memory_mb, method) "
                "VALUES (?, ?, ?, ?, ?)",
                (file_id, stage, duration_ms, memory_mb, method),
            )


# =============================================================================
# Helpers
# =============================================================================

def _serialise_fields(fields) -> str:
    """Serialise an ExtractedFields or None to a JSON string."""
    if fields is None:
        return ""
    try:
        return json.dumps(asdict(fields), default=str)
    except (TypeError, ValueError):
        return "{}"
