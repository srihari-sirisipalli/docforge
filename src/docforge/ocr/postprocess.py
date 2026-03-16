"""
DocForge — OCR Text Post-processing
======================================

Cleans up raw OCR output to improve heuristic extraction accuracy:
  - Fix common ligature errors (fi, fl)
  - Fix OCR character swaps (rn→m, l→1)
  - Normalise whitespace
  - Re-join hyphenated line breaks
"""

from __future__ import annotations

import re


# Common OCR character confusions
CHAR_FIXES = [
    ("\ufb01", "fi"),   # fi ligature
    ("\ufb02", "fl"),   # fl ligature
    ("\u2018", "'"),    # Left single quote
    ("\u2019", "'"),    # Right single quote
    ("\u201c", '"'),    # Left double quote
    ("\u201d", '"'),    # Right double quote
    ("\u2013", "-"),    # En dash
    ("\u2014", "--"),   # Em dash
    ("\u2022", "*"),    # Bullet
]


def postprocess_ocr_text(text: str) -> str:
    """Clean up raw OCR output for better heuristic extraction.

    Args:
        text: Raw OCR text.

    Returns:
        Cleaned text.
    """
    if not text:
        return ""

    # Step 1: Fix ligatures and special characters
    for old, new in CHAR_FIXES:
        text = text.replace(old, new)

    # Step 2: Normalise whitespace (collapse multiple spaces/tabs)
    text = re.sub(r'[ \t]+', ' ', text)

    # Step 3: Re-join hyphenated line breaks
    # "docu-\nment" → "document"
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

    # Step 4: Normalise line endings
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Step 5: Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()
