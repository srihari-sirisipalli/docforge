"""
DocForge — Extractors Package
===============================

All extraction modules for the five-stage pipeline:
  Stage 1: MetadataExtractor  — PDF Info dict
  Stage 2: PageRenderer       — PDF → PNG images
           TextExtractor      — Embedded text + quality scoring
  Stage 3: HeuristicExtractor — Regex/rules on text (Path B)
           VLMExtractor       — Vision model on images (Path A, in vlm/)
           OCREngine          — OCR fallback (Path C, in ocr/)
  Stage 4: FieldMerger        — Confidence-weighted reconciliation
"""

from docforge.extractors.heuristic import HeuristicExtractor
from docforge.extractors.merger import FieldMerger
from docforge.extractors.metadata import MetadataExtractor, compute_file_id
from docforge.extractors.renderer import PageRenderer
from docforge.extractors.text import TextExtractor, TextQualityScorer

__all__ = [
    "MetadataExtractor", "compute_file_id",
    "PageRenderer",
    "TextExtractor", "TextQualityScorer",
    "HeuristicExtractor",
    "FieldMerger",
]
