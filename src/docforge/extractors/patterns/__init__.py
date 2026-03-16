"""
DocForge — Extraction Pattern Library
=======================================

Regex patterns, heuristic rules, and domain-specific signal detection
for dates, authors, identifiers, and document types.
"""

from docforge.extractors.patterns.authors import AUTHOR_PATTERNS, extract_author
from docforge.extractors.patterns.dates import DATE_PATTERNS, extract_date
from docforge.extractors.patterns.doctypes import (
    classify_document_type,
    classify_maritime_document,
)
from docforge.extractors.patterns.identifiers import (
    REPORT_ID_PATTERNS,
    extract_report_id,
)

__all__ = [
    "extract_date", "DATE_PATTERNS",
    "extract_author", "AUTHOR_PATTERNS",
    "extract_report_id", "REPORT_ID_PATTERNS",
    "classify_document_type", "classify_maritime_document",
]
