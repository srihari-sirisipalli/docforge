"""
DocForge — Filename Sanitiser
================================

Ensures filenames are safe across all major operating systems:
  - Strips accents (é → e, ü → u)
  - Removes illegal characters (<>:"/\\|?*)
  - Normalises whitespace and separators
  - Enforces maximum length
  - Handles edge cases (reserved names, leading dots)
"""

from __future__ import annotations

import re

from unidecode import unidecode


def sanitise_filename(
    text: str,
    separator: str = "_",
    lowercase: bool = True,
    strip_accents: bool = True,
    max_length: int = 120,
) -> str:
    """Sanitise a string for use as a filename.

    Args:
        text:          Raw text to convert to a filename.
        separator:     Character to use in place of spaces/dashes.
        lowercase:     Convert to lowercase.
        strip_accents: Remove diacritical marks (accents).
        max_length:    Maximum filename length (excluding extension).

    Returns:
        Safe filename string (without extension).

    Examples:
        >>> sanitise_filename("DNV — Rules for Steel Ships (Part 3)")
        'dnv_rules_for_steel_ships_part_3'
        >>> sanitise_filename("Wärtsilä 12V46F Engine Manual")
        'wartsila_12v46f_engine_manual'
    """
    if not text:
        return ""

    # Step 1: Strip accents (Unicode → ASCII)
    if strip_accents:
        text = unidecode(text)

    # Step 2: Lowercase
    if lowercase:
        text = text.lower()

    # Step 3: Remove illegal filesystem characters
    # Windows: < > : " / \ | ? *
    # Also remove control characters
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)

    # Step 4: Replace whitespace, dashes, and other separators
    text = re.sub(r'[\s\-–—_.,;:!@#$%^&*()\[\]{}]+', separator, text)

    # Step 5: Collapse multiple separators
    text = re.sub(f'{re.escape(separator)}+', separator, text)

    # Step 6: Strip leading/trailing separators
    text = text.strip(separator)

    # Step 7: Enforce maximum length
    if len(text) > max_length:
        text = text[:max_length].rstrip(separator)

    # Step 8: Handle Windows reserved names
    reserved = {
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    }
    if text.lower() in reserved:
        text = f"{text}{separator}file"

    return text
