"""
DocForge — Organizer Package
===============================

Folder organisation strategies for document structure.
"""

from docforge.organizer.strategies import STRATEGY_REGISTRY, get_strategy
from docforge.organizer.tree_builder import FolderOrganizer

__all__ = ["FolderOrganizer", "get_strategy", "STRATEGY_REGISTRY"]
