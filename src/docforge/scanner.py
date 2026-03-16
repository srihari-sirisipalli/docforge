"""
DocForge — Directory Scanner
==============================

Recursively scans directories for PDF files and creates PendingDocument
records for each discovered file. Handles:
  - Recursive/non-recursive scanning
  - Symlink following (configurable)
  - Hidden file/directory skipping
  - File size filtering (min/max)
  - Deduplication via file_id (SHA-256)

The scanner is intentionally simple — it only collects file identity.
All heavy processing is deferred to the pipeline stages.
"""

from __future__ import annotations

import os
from pathlib import Path

from docforge.extractors.metadata import compute_file_id
from docforge.infra.config import ScannerConfig
from docforge.infra.logging import get_logger
from docforge.models.record import PendingDocument

logger = get_logger(__name__)


class DirectoryScanner:
    """Scans directories for PDF files and produces PendingDocument records.

    Thread-safe: stateless after init, can be used from any thread.
    """

    def __init__(self, config: ScannerConfig | None = None):
        """
        Args:
            config: Scanner configuration. Uses defaults if None.
        """
        self.config = config or ScannerConfig()

    def scan(self, source: str) -> list[PendingDocument]:
        """Scan a directory (or single file) for PDFs.

        Args:
            source: Path to a directory or a single PDF file.

        Returns:
            List of PendingDocument records, one per discovered PDF.
        """
        source_path = Path(source).expanduser().resolve()

        if not source_path.exists():
            logger.error("Source path does not exist: %s", source_path)
            return []

        # Single file mode
        if source_path.is_file():
            if self._matches(source_path):
                return [self._create_pending(source_path)]
            logger.warning("Not a matching file: %s", source_path)
            return []

        # Directory mode
        if not source_path.is_dir():
            logger.error("Source is not a file or directory: %s", source_path)
            return []

        logger.info("Scanning: %s (recursive=%s)", source_path, self.config.recursive)

        documents: list[PendingDocument] = []
        seen_ids: set[str] = set()
        skipped = 0

        iterator = (
            source_path.rglob("*") if self.config.recursive
            else source_path.glob("*")
        )

        for filepath in sorted(iterator):
            # Skip directories
            if not filepath.is_file():
                continue

            # Skip symlinks if configured
            if filepath.is_symlink() and not self.config.follow_symlinks:
                continue

            # Skip hidden files/directories
            if self.config.skip_hidden and _is_hidden(filepath, source_path):
                continue

            # Check file pattern match
            if not self._matches(filepath):
                continue

            # Check file size bounds
            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            if size < self.config.min_file_size:
                skipped += 1
                continue
            if size > self.config.max_file_size:
                skipped += 1
                logger.debug("Skipping oversized file (%d bytes): %s", size, filepath.name)
                continue

            # Compute file_id for deduplication
            try:
                file_id = compute_file_id(str(filepath))
            except OSError as exc:
                logger.warning("Cannot read file %s: %s", filepath, exc)
                continue

            if file_id in seen_ids:
                logger.debug("Duplicate file skipped: %s", filepath.name)
                skipped += 1
                continue
            seen_ids.add(file_id)

            documents.append(PendingDocument(
                file_id=file_id,
                original_path=str(filepath),
                file_size_bytes=size,
            ))

        logger.info(
            "Scan complete: %d PDFs found, %d skipped (in %s)",
            len(documents), skipped, source_path,
        )
        return documents

    def _matches(self, filepath: Path) -> bool:
        """Check if a file matches the configured patterns."""
        return any(filepath.match(p) for p in self.config.file_patterns)

    @staticmethod
    def _create_pending(filepath: Path) -> PendingDocument:
        """Create a PendingDocument from a single file path."""
        file_id = compute_file_id(str(filepath))
        size = filepath.stat().st_size
        return PendingDocument(
            file_id=file_id,
            original_path=str(filepath),
            file_size_bytes=size,
        )


def _is_hidden(filepath: Path, root: Path) -> bool:
    """Check if any path component (relative to root) starts with a dot."""
    try:
        relative = filepath.relative_to(root)
        return any(part.startswith(".") for part in relative.parts)
    except ValueError:
        return filepath.name.startswith(".")
