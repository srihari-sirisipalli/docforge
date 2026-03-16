"""
DocForge — Filename Collision Resolution
==========================================

Resolves duplicate filenames across the document corpus. When two
documents produce the same canonical name, a suffix or hash is
appended to make them unique.

Strategies:
  - suffix: Append _02, _03, etc. (default, human-readable)
  - hash:   Append _a1b2c3d4 (8 chars of file_id, always unique)
"""

from __future__ import annotations

import os

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class CollisionResolver:
    """Resolves duplicate filenames across a batch of documents.

    Tracks all generated names and appends suffixes when collisions occur.
    """

    def __init__(self, strategy: str = "suffix"):
        """
        Args:
            strategy: "suffix" for _02/_03 numbering, "hash" for file_id snippet.
        """
        self.strategy = strategy
        self.seen_names: dict[str, int] = {}

    def resolve(self, filename: str, file_id: str) -> str:
        """Check for collision and resolve if needed.

        Args:
            filename: Proposed filename (with extension).
            file_id:  Document's unique identifier.

        Returns:
            Final filename, modified if collision detected.
        """
        base_key = filename.lower()

        if base_key not in self.seen_names:
            self.seen_names[base_key] = 1
            return filename

        # Collision detected
        self.seen_names[base_key] += 1
        name, ext = os.path.splitext(filename)

        if self.strategy == "hash":
            resolved = f"{name}_{file_id[:8]}{ext}"
        else:  # suffix
            count = self.seen_names[base_key]
            resolved = f"{name}_{count:02d}{ext}"

        logger.debug(
            "  Collision resolved: '%s' → '%s' (count=%d)",
            filename, resolved, self.seen_names[base_key],
        )

        return resolved

    def reset(self) -> None:
        """Clear the collision tracking state."""
        self.seen_names.clear()
