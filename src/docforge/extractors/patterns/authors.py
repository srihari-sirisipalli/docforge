"""
DocForge — Author Extraction Patterns
=======================================

Extracts author names from document text using regex patterns,
positional heuristics, and PDF metadata.

Handles formats like:
  - "Author: John Smith"
  - "By Dr. Jane M. Doe"
  - "Prepared by: Kumar, R. and Patel, S."
  - First line author names in research papers
"""

from __future__ import annotations

import re

from docforge.models.fields import FieldValue


# =============================================================================
# Author Patterns
# =============================================================================
# Each tuple: (regex_pattern, confidence)

AUTHOR_PATTERNS: list[tuple[str, float]] = [
    # Explicit label: "Author: John Smith" or "Written by: Jane Doe"
    (r'(?:Author|Authors|Written\s+by|Prepared\s+by|Compiled\s+by'
     r'|Submitted\s+by|Drafted\s+by)[:\s]+'
     r'([A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+(?:\s+(?:and|&)\s+'
     r'[A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+)*)', 0.85),

    # "Dr. / Prof. / Eng." prefix
    (r'(?:Dr|Prof|Eng|Mr|Mrs|Ms)\.?\s+'
     r'([A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+)', 0.70),

    # "Last, First" format (common in technical reports)
    (r'([A-Z][a-z]+,\s+[A-Z](?:\.|[a-z]+)(?:\s+[A-Z]\.)*)', 0.75),

    # Name at start of line followed by comma or "and" (research papers)
    (r'^([A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+)\s*'
     r'(?:,|\band\b|\n)', 0.50),

    # Name followed by affiliation indicator
    (r'([A-Z][a-z]+(?:\s+[A-Z]\.?)*\s+[A-Z][a-z]+)\s*'
     r'(?:\d|\(|,\s*(?:Ph\.?D|M\.?Sc|B\.?Eng))', 0.65),
]

# Words that look like names but aren't (common false positives)
AUTHOR_BLACKLIST = {
    "table of", "figure", "section", "chapter", "appendix",
    "page", "revision", "version", "document", "report",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "international maritime", "classification society",
    "executive summary", "terms conditions", "table contents",
}


# =============================================================================
# Author Extraction
# =============================================================================

def extract_author(text: str, metadata: dict) -> FieldValue:
    """Extract the primary author name from text and metadata.

    Tries PDF metadata first, then scans text with regex patterns.
    Multiple authors are formatted as "Last, First et al." if > 3.

    Args:
        text:     Document text (first ~3000 chars recommended).
        metadata: PDF Info dictionary.

    Returns:
        FieldValue with the best author candidate.
    """
    candidates: list[FieldValue] = []

    # ── Strategy 1: PDF metadata /Author ────────────────────────────────
    for key in ("author", "Author"):
        if key in metadata and metadata[key]:
            author = str(metadata[key]).strip()
            if len(author) > 2 and not _is_garbage_author(author):
                candidates.append(FieldValue(
                    value=_normalise_author(author),
                    confidence=0.70,
                    source="metadata",
                    extraction_method="pdf_info_author",
                ))

    # ── Strategy 2: Regex patterns on text ──────────────────────────────
    search_text = text[:3000] if text else ""
    for pattern, conf in AUTHOR_PATTERNS:
        for match in re.finditer(pattern, search_text, re.MULTILINE):
            author = match.group(1).strip()
            if not _is_garbage_author(author) and 3 < len(author) < 100:
                candidates.append(FieldValue(
                    value=_normalise_author(author),
                    confidence=conf,
                    source="heuristic",
                    extraction_method=f"regex:author_pattern",
                ))

    if candidates:
        return max(candidates, key=lambda c: c.confidence)

    return FieldValue(value=None, confidence=0.0, source="heuristic",
                      extraction_method="no_author_found")


def extract_author_last_name(author_value: str | None) -> str:
    """Extract just the last name from an author string.

    Handles formats: "John Smith", "Smith, John", "Smith, J.", "J. Smith"

    Args:
        author_value: Full author name string.

    Returns:
        Last name string, or empty string.
    """
    if not author_value:
        return ""

    author = author_value.strip()

    # Handle "et al." — use first author only
    author = re.sub(r'\s+et\s+al\.?', '', author)

    # "Last, First" format
    if "," in author:
        return author.split(",")[0].strip()

    # "First Last" or "F. M. Last" format
    parts = author.split()
    if parts:
        return parts[-1].strip()

    return ""


def _normalise_author(author: str) -> str:
    """Normalise author name formatting.

    Removes extra whitespace, standardises "and" separators.
    """
    author = re.sub(r'\s+', ' ', author.strip())
    # Remove trailing punctuation
    author = author.rstrip('.,;:')
    return author


def _is_garbage_author(author: str) -> bool:
    """Check if an author string is likely garbage (not a real name)."""
    lower = author.lower().strip()

    # Too short or too long
    if len(lower) < 3 or len(lower) > 100:
        return True

    # Known non-author strings
    for blacklisted in AUTHOR_BLACKLIST:
        if blacklisted in lower:
            return True

    # All digits or mostly non-alpha
    alpha_ratio = sum(c.isalpha() or c.isspace() for c in lower) / max(len(lower), 1)
    if alpha_ratio < 0.7:
        return True

    # Common software-generated author fields
    if any(s in lower for s in [
        "microsoft", "adobe", "scanner", "unknown", "user",
        "admin", "root", "system", "pdf", ".exe",
    ]):
        return True

    return False
