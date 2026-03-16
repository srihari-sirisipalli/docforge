"""
DocForge — Date Extraction Patterns
=====================================

Extracts dates from document text using multiple regex strategies,
contextual boosting, and PDF metadata date parsing.

Handles ISO dates, US/EU formats, written months, year-only references,
and PDF date strings (D:20190315120000+05'30').
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from dateutil import parser as dateutil_parser

from docforge.models.fields import FieldValue


# =============================================================================
# Date Patterns
# =============================================================================
# Each tuple: (regex_pattern, base_confidence, format_name)
# Higher base confidence = more specific/reliable pattern.

DATE_PATTERNS: list[tuple[str, float, str]] = [
    # ISO 8601: 2019-03-15
    (r'(\d{4})-(\d{2})-(\d{2})', 0.95, "iso"),

    # US format: 03/15/2019 or 3/15/2019
    (r'(\d{1,2})/(\d{1,2})/(\d{4})', 0.80, "us"),

    # European format: 15.03.2019
    (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', 0.80, "eu"),

    # Written month: March 15, 2019 or March 2019
    (r'(January|February|March|April|May|June|July|August|September|'
     r'October|November|December)\s+(\d{1,2}),?\s+(\d{4})', 0.90, "written_full"),

    # Month + year: March 2019
    (r'(January|February|March|April|May|June|July|August|September|'
     r'October|November|December)\s+(\d{4})', 0.70, "month_year"),

    # Abbreviated month: Mar 2019, 15-Mar-2019
    (r'(\d{1,2})[-\s](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
     r'[-\s](\d{4})', 0.85, "abbrev_dmy"),

    (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
     r'[-\s](\d{4})', 0.65, "abbrev_my"),

    # Year only: standalone four-digit year between 1950 and 2030
    (r'\b((?:19[5-9]\d|20[0-3]\d))\b', 0.30, "year_only"),
]

# Contextual keywords near a date that boost confidence
CONTEXT_BOOST: dict[str, float] = {
    "published": 0.15,
    "date": 0.10,
    "dated": 0.10,
    "copyright": 0.10,
    "revised": 0.08,
    "revision": 0.08,
    "edition": 0.08,
    "created": 0.05,
    "issued": 0.10,
    "effective": 0.10,
    "approved": 0.08,
}

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


# =============================================================================
# Date Extraction
# =============================================================================

def extract_date(text: str, metadata: dict) -> FieldValue:
    """Extract the most likely publication/creation date from text and metadata.

    Tries PDF metadata dates first, then scans text with regex patterns.
    Contextual keywords near the date boost confidence.

    Args:
        text:     Document text (first ~5000 chars recommended).
        metadata: PDF Info dictionary.

    Returns:
        FieldValue with the best date candidate.
    """
    candidates: list[FieldValue] = []

    # ── Strategy 1: PDF metadata dates ──────────────────────────────────
    for key in ("creationDate", "modDate", "CreationDate", "ModDate"):
        if key in metadata and metadata[key]:
            parsed = parse_pdf_date(str(metadata[key]))
            if parsed:
                candidates.append(FieldValue(
                    value=parsed.strftime("%Y-%m-%d"),
                    confidence=0.60,
                    source="metadata",
                    extraction_method=f"pdf_{key}",
                ))

    # ── Strategy 2: Regex patterns on text ──────────────────────────────
    search_text = text[:5000] if text else ""
    for pattern, base_conf, fmt in DATE_PATTERNS:
        for match in re.finditer(pattern, search_text, re.IGNORECASE):
            conf = base_conf

            # Context boosting: check surrounding text for date keywords
            start = max(0, match.start() - 60)
            end = min(len(search_text), match.end() + 60)
            context = search_text[start:end].lower()

            for keyword, boost in CONTEXT_BOOST.items():
                if keyword in context:
                    conf = min(conf + boost, 1.0)

            # Parse the matched date
            parsed = _parse_match(match, fmt)
            if parsed and 1950 <= parsed.year <= 2035:
                candidates.append(FieldValue(
                    value=parsed.strftime("%Y-%m-%d") if fmt != "year_only"
                          else str(parsed.year),
                    confidence=conf,
                    source="heuristic",
                    extraction_method=f"regex:{fmt}",
                ))

    # Return highest-confidence candidate
    if candidates:
        return max(candidates, key=lambda c: c.confidence)

    return FieldValue(value=None, confidence=0.0, source="heuristic",
                      extraction_method="no_date_found")


def extract_year(date_value: str | None) -> Optional[str]:
    """Extract a 4-digit year from a date string.

    Args:
        date_value: A date string like '2019-03-15' or '2019'.

    Returns:
        Year string like '2019', or None.
    """
    if not date_value:
        return None
    match = re.search(r'\b((?:19|20)\d{2})\b', str(date_value))
    return match.group(1) if match else None


def parse_pdf_date(date_str: str) -> Optional[datetime]:
    """Parse a PDF date string like D:20190315120000+05'30'.

    Args:
        date_str: Raw date string from PDF metadata.

    Returns:
        datetime object, or None if parsing fails.
    """
    if not date_str:
        return None

    # Strip the D: prefix
    cleaned = date_str.strip()
    if cleaned.startswith("D:"):
        cleaned = cleaned[2:]

    # Remove timezone info (simplified — just extract the date part)
    cleaned = re.sub(r"[+\-Z].*$", "", cleaned)

    try:
        if len(cleaned) >= 8:
            return datetime.strptime(cleaned[:8], "%Y%m%d")
        elif len(cleaned) >= 4:
            return datetime.strptime(cleaned[:4], "%Y")
    except ValueError:
        pass

    # Fallback: use dateutil for fuzzy parsing
    try:
        return dateutil_parser.parse(date_str, fuzzy=True)
    except (ValueError, OverflowError):
        return None


def _parse_match(match: re.Match, fmt: str) -> Optional[datetime]:
    """Parse a regex match into a datetime based on the format name."""
    try:
        groups = match.groups()

        if fmt == "iso":
            return datetime(int(groups[0]), int(groups[1]), int(groups[2]))

        elif fmt == "us":
            return datetime(int(groups[2]), int(groups[0]), int(groups[1]))

        elif fmt == "eu":
            return datetime(int(groups[2]), int(groups[1]), int(groups[0]))

        elif fmt == "written_full":
            month = MONTH_MAP.get(groups[0].lower(), 1)
            return datetime(int(groups[2]), month, int(groups[1]))

        elif fmt in ("month_year", "abbrev_my"):
            month = MONTH_MAP.get(groups[0].lower(), 1)
            return datetime(int(groups[1]), month, 1)

        elif fmt == "abbrev_dmy":
            month = MONTH_MAP.get(groups[1].lower(), 1)
            return datetime(int(groups[2]), month, int(groups[0]))

        elif fmt == "year_only":
            return datetime(int(groups[0]), 1, 1)

    except (ValueError, IndexError):
        return None

    return None
