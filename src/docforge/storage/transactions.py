"""
DocForge — Transaction Manager
================================

Provides atomic, rollback-safe file operations. Every rename/move is
logged BEFORE execution and can be reversed in strict reverse order
if anything goes wrong mid-batch.

The transaction log uses the operations table in the state database
as a write-ahead log (WAL pattern for file operations).

Usage:
    txn = TransactionManager(db)
    success = txn.execute_batch(job_id, operations)
    if not success:
        txn.rollback_job(job_id)  # Automatic on failure
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from docforge.infra.logging import get_logger
from docforge.storage.database import StateDB

logger = get_logger(__name__)


class RollbackError(Exception):
    """Raised when a rollback operation itself fails."""
    pass


class TransactionManager:
    """Manages atomic file operations with WAL-based rollback support.

    All file operations (rename, move, mkdir) are:
      1. Logged to the database BEFORE execution
      2. Executed one by one
      3. Marked as executed in the database
      4. Rolled back in reverse order if any operation fails
    """

    def __init__(self, db: StateDB):
        self.db = db

    def execute_batch(self, job_id: str, operations: list[dict]) -> bool:
        """Execute a batch of file operations with transaction safety.

        If any operation fails, all previously executed operations in this
        batch are rolled back automatically.

        Args:
            job_id:     Parent job ID for rollback tracking.
            operations: List of operation dicts, each with:
                        file_id, operation, source_path, target_path.

        Returns:
            True if all operations succeeded, False if rolled back.
        """
        if not operations:
            logger.info("No operations to execute.")
            return True

        logger.info(
            "Executing batch: %d operations for job %s",
            len(operations), job_id,
        )

        # Phase 1: Log all operations (WAL write)
        op_ids = []
        for op in operations:
            op_id = self.db.log_operation(job_id, op)
            op_ids.append(op_id)

        # Phase 2: Execute operations one by one
        executed = []
        try:
            for op, op_id in zip(operations, op_ids):
                self._execute_single(op)
                self.db.mark_operation_executed(op_id)
                executed.append((op, op_id))

                if len(executed) % 100 == 0:
                    logger.info(
                        "  Progress: %d / %d operations completed",
                        len(executed), len(operations),
                    )

        except Exception as exc:
            logger.error(
                "Operation failed at %d / %d: %s — initiating rollback",
                len(executed), len(operations), exc,
            )
            self._rollback_executed(executed)
            return False

        logger.info(
            "Batch complete: %d operations executed successfully", len(operations),
        )
        return True

    def rollback_job(self, job_id: str) -> int:
        """Roll back ALL executed operations for a job, in reverse order.

        Args:
            job_id: The job to roll back.

        Returns:
            Number of operations rolled back.

        Raises:
            RollbackError: If a rollback operation itself fails.
        """
        operations = self.db.get_executed_operations(job_id, order="DESC")

        if not operations:
            logger.info("No executed operations to roll back for job %s", job_id)
            return 0

        logger.info(
            "Rolling back %d operations for job %s...", len(operations), job_id,
        )

        rolled_back = 0
        for op in operations:
            try:
                self._reverse_operation(op)
                self.db.mark_operation_rolled_back(op["op_id"])
                rolled_back += 1
            except Exception as exc:
                logger.error(
                    "Rollback failed at operation %d (%s → %s): %s",
                    op["op_id"], op["target_path"], op["source_path"], exc,
                )
                raise RollbackError(
                    f"Cannot rollback operation {op['op_id']}: {exc}"
                ) from exc

        logger.info("Rollback complete: %d operations reversed", rolled_back)
        return rolled_back

    # =====================================================================
    # Internal Methods
    # =====================================================================

    def _execute_single(self, op: dict) -> None:
        """Execute a single file operation.

        Args:
            op: Operation dict with 'operation', 'source_path', 'target_path'.

        Raises:
            OSError: If the file operation fails.
        """
        operation = op["operation"]
        source = op["source_path"]
        target = op["target_path"]

        if operation == "mkdir":
            Path(target).mkdir(parents=True, exist_ok=True)
            logger.debug("  mkdir: %s", target)

        elif operation in ("rename", "move"):
            # Ensure target directory exists
            Path(target).parent.mkdir(parents=True, exist_ok=True)

            # Safety check: source must exist, target must not
            if not os.path.exists(source):
                raise FileNotFoundError(f"Source file missing: {source}")
            if os.path.exists(target):
                raise FileExistsError(f"Target already exists: {target}")

            shutil.move(source, target)
            logger.debug("  %s: %s → %s", operation, source, target)

        else:
            raise ValueError(f"Unknown operation type: {operation}")

    def _reverse_operation(self, op: dict) -> None:
        """Reverse a single executed operation.

        Args:
            op: Operation dict from the database.
        """
        operation = op["operation"]

        if operation in ("rename", "move"):
            source = op["target_path"]   # Was moved TO here
            target = op["source_path"]   # Move it BACK
            if os.path.exists(source):
                Path(target).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(source, target)
                logger.debug("  rollback %s: %s → %s", operation, source, target)
            else:
                logger.warning(
                    "  rollback skip: target file no longer exists: %s", source,
                )

        elif operation == "mkdir":
            target = op["target_path"]
            if os.path.isdir(target) and not os.listdir(target):
                os.rmdir(target)
                logger.debug("  rollback mkdir: removed %s", target)

    def _rollback_executed(self, executed: list[tuple[dict, int]]) -> None:
        """Roll back a list of (operation, op_id) tuples in reverse order."""
        for op, op_id in reversed(executed):
            try:
                self._reverse_operation(op)
                self.db.mark_operation_rolled_back(op_id)
            except Exception as exc:
                logger.error("Rollback failed for op %d: %s", op_id, exc)


def compute_file_checksum(path: str) -> str:
    """Compute SHA-256 checksum of a file for integrity verification.

    Args:
        path: Path to the file.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()
