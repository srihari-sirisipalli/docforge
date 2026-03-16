"""
DocForge — Folder Organisation Tree Builder
==============================================

Computes target folder paths for documents based on the selected
organisation strategy. Does NOT create directories — that's the
renamer's job.
"""

from __future__ import annotations

from pathlib import Path

from docforge.infra.logging import get_logger
from docforge.models.fields import ExtractedFields
from docforge.organizer.strategies import get_strategy

logger = get_logger(__name__)


class FolderOrganizer:
    """Computes target paths for document organisation."""

    def __init__(self, strategy: str, base_dir: str):
        """
        Args:
            strategy: Organisation strategy name (e.g., "type", "domain_type").
            base_dir: Root directory for the organised output.
        """
        self.strategy_fn = get_strategy(strategy)
        self.strategy_name = strategy
        self.base_dir = Path(base_dir)

    def compute_target(self, fields: ExtractedFields, filename: str) -> str:
        """Compute the full target path for a document.

        Args:
            fields:   Merged ExtractedFields for the document.
            filename: Canonical filename (from the name generator).

        Returns:
            Full target path as a string.
        """
        relative_dir = self.strategy_fn(fields)
        target = self.base_dir / relative_dir / filename
        return str(target)

    def compute_target_dir(self, fields: ExtractedFields) -> str:
        """Compute just the target directory (without filename).

        Args:
            fields: Merged ExtractedFields for the document.

        Returns:
            Target directory path as a string.
        """
        relative_dir = self.strategy_fn(fields)
        return str(self.base_dir / relative_dir)
