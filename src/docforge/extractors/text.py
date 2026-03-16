"""
DocForge — Stage 2: Text Extractor & Quality Scorer
=====================================================

Extracts embedded text from PDF pages using PyMuPDF and scores its
quality. The quality score determines whether the document takes the
fast path (heuristic) or the VLM path.

Quality scoring uses three signals:
  1. Character entropy — real text has higher entropy than OCR garbage
  2. Dictionary hit rate — real words vs. random character sequences
  3. Whitespace ratio — properly formatted text has natural spacing
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter

import fitz  # PyMuPDF

from docforge.infra.logging import get_logger
from docforge.models.fields import FieldValue

logger = get_logger(__name__)

# Top 500 most common English words — sufficient for quality scoring
# without needing an external dictionary file.
COMMON_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "great", "between", "need", "under",
    "may", "should", "very", "each", "much", "where", "right", "still",
    "own", "before", "same", "through", "being", "long", "since",
    "both", "might", "been", "part", "every", "must", "point", "such",
    # Technical / maritime terms for better scoring on domain docs
    "shall", "section", "chapter", "table", "figure", "page", "report",
    "design", "analysis", "system", "data", "ship", "vessel", "marine",
    "offshore", "structure", "load", "stress", "steel", "class",
    "safety", "operation", "equipment", "engine", "cargo", "ballast",
    "survey", "inspection", "certificate", "rules", "code", "standard",
    "international", "regulation", "procedure", "manual", "plan",
    "document", "reference", "appendix", "note", "guide", "drawing",
    "requirement", "applicable", "compliance", "installation",
    "maintenance", "test", "result", "value", "pressure", "temperature",
    "material", "specification", "type", "model", "number", "date",
    "total", "maximum", "minimum", "above", "below", "following",
}


class TextExtractor:
    """Extracts embedded text from PDF pages using PyMuPDF.

    Populates the document record with raw_text and text_quality_score.
    The quality score is the key routing decision: high quality → fast path,
    low quality → VLM path.
    """

    def __init__(self, max_pages: int = 5):
        """
        Args:
            max_pages: Maximum number of pages to extract text from.
        """
        self.max_pages = max_pages

    def extract(self, pdf_path: str) -> tuple[str, float]:
        """Extract text and compute quality score.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Tuple of (extracted_text, quality_score).
        """
        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            logger.warning("Cannot open PDF for text extraction: %s — %s", pdf_path, exc)
            return "", 0.0

        try:
            pages_to_read = min(self.max_pages, len(doc))
            text_parts: list[str] = []

            for page_num in range(pages_to_read):
                page = doc[page_num]
                page_text = page.get_text("text")
                if page_text:
                    text_parts.append(page_text)

            full_text = "\n".join(text_parts)
            quality = TextQualityScorer.score(full_text)

            logger.debug(
                "  Text extraction: %d pages, %d chars, quality=%.2f",
                pages_to_read, len(full_text), quality,
            )

            return full_text, quality

        finally:
            doc.close()


class TextQualityScorer:
    """Scores the quality of extracted text on a 0.0–1.0 scale.

    High-quality text (>0.7) indicates a clean digital PDF suitable for
    heuristic extraction. Low-quality text (<0.3) indicates a scanned
    document that needs VLM or OCR processing.

    Scoring signals:
      - Character entropy: real text has entropy around 4.0–5.0
      - Dictionary hit rate: what fraction of words are real English words
      - Whitespace ratio: properly formatted text has ~15% spaces
    """

    @staticmethod
    def score(text: str) -> float:
        """Score text quality from 0.0 (garbage/empty) to 1.0 (clean text).

        Args:
            text: The extracted text to score.

        Returns:
            Quality score as a float.
        """
        if not text or len(text.strip()) < 10:
            return 0.0

        scores: list[float] = []

        # ── Signal 1: Character entropy ─────────────────────────────────
        # Real text has entropy ~4.0-5.0, garbage has lower or higher.
        entropy = _char_entropy(text)
        entropy_score = min(entropy / 4.5, 1.0)
        scores.append(entropy_score)

        # ── Signal 2: Dictionary hit rate ───────────────────────────────
        # What fraction of 3+ letter words are in our common word list?
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        if words:
            hits = sum(1 for w in words if w in COMMON_WORDS)
            dict_score = hits / len(words)
            scores.append(min(dict_score * 2.5, 1.0))  # Boost: 40% hit rate → 1.0

        # ── Signal 3: Whitespace ratio ──────────────────────────────────
        # Well-formatted text has ~12-18% spaces.
        space_count = text.count(' ') + text.count('\n')
        ws_ratio = space_count / max(len(text), 1)
        ws_score = 1.0 - abs(ws_ratio - 0.15) * 5  # Peak at 15%
        scores.append(max(ws_score, 0.0))

        # ── Signal 4: Line length consistency ───────────────────────────
        # Real documents have consistent line lengths; garbage doesn't.
        lines = [line for line in text.split('\n') if len(line.strip()) > 5]
        if len(lines) >= 3:
            lengths = [len(line) for line in lines[:50]]
            if len(lengths) >= 3:
                mean_len = statistics.mean(lengths)
                if mean_len > 10:
                    cv = statistics.stdev(lengths) / mean_len  # Coefficient of variation
                    # CV < 0.5 means fairly consistent → good
                    consistency_score = max(0.0, 1.0 - cv)
                    scores.append(consistency_score)

        return statistics.mean(scores) if scores else 0.0


def _char_entropy(text: str) -> float:
    """Calculate Shannon entropy of a text string.

    Args:
        text: Input text.

    Returns:
        Entropy in bits.
    """
    if not text:
        return 0.0

    counts = Counter(text)
    total = len(text)

    entropy = 0.0
    for count in counts.values():
        if count > 0:
            prob = count / total
            entropy -= prob * math.log2(prob)

    return entropy
