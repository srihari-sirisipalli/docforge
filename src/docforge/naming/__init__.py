"""
DocForge — Naming Package
============================

Per-type naming templates, filename generation, and collision resolution.
"""

from docforge.naming.collision import CollisionResolver
from docforge.naming.generator import FilenameGenerator
from docforge.naming.sanitizer import sanitise_filename
from docforge.naming.templates import TEMPLATE_REGISTRY, get_template_for_type

__all__ = [
    "FilenameGenerator", "CollisionResolver",
    "sanitise_filename", "get_template_for_type", "TEMPLATE_REGISTRY",
]
