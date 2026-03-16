"""
DocForge — Stage 3 Path B: Heuristic Extractor
================================================

Rule-based field extraction using regex patterns, positional analysis,
and domain-specific signal detection. This is the "fast path" —
runs on embedded text without needing a VLM or OCR.

The heuristic extractor serves two roles:
  1. Standalone extractor (Path B) when VLM is unavailable
  2. Cross-validator when used alongside VLM (VLM_PLUS_HEURISTIC strategy)

Extraction order:
  1. Title (largest font, first significant line, regex patterns)
  2. Author (explicit labels, name patterns)
  3. Organisation (known maritime org matching)
  4. Date (regex with context boosting)
  5. Report ID (DOI, ISBN, classification society references)
  6. Document type (generic + maritime-specific signal scoring)
"""

from __future__ import annotations

import re
import time

import fitz  # PyMuPDF

from docforge.extractors.patterns.authors import extract_author
from docforge.extractors.patterns.dates import extract_date, extract_year
from docforge.extractors.patterns.doctypes import (
    classify_document_type,
    classify_maritime_document,
    detect_organisation,
)
from docforge.extractors.patterns.identifiers import extract_report_id
from docforge.infra.logging import get_logger
from docforge.models.fields import ExtractedFields, FieldValue

logger = get_logger(__name__)


class HeuristicExtractor:
    """Stage 3 Path B: Extract metadata using regex and heuristic rules.

    Works on embedded text (no model required). Fast (~5-20 ms per doc).
    Populates heuristic_fields on the DocumentRecord.
    """

    def process(self, record) -> None:
        """Run heuristic extraction on a document record.

        Requires record.raw_text to be populated (by TextExtractor).
        Populates record.heuristic_fields with all extracted fields.

        Args:
            record: DocumentRecord with raw_text available.
        """
        start = time.perf_counter()
        text = record.raw_text
        metadata = record.pdf_metadata
        path = record.original_path

        logger.debug("Stage 3 (heuristic) — Extracting: %s", record.file_id[:12])

        fields = ExtractedFields()

        # ── Title extraction ────────────────────────────────────────────
        fields.title = self._extract_title(text, metadata, path)

        # ── Author extraction ───────────────────────────────────────────
        fields.author = extract_author(text, metadata)

        # ── Organisation detection ──────────────────────────────────────
        fields.organization = detect_organisation(text, metadata)

        # ── Date extraction ─────────────────────────────────────────────
        fields.date = extract_date(text, metadata)
        if not fields.date.is_empty():
            year = extract_year(fields.date.value)
            if year:
                fields.year = FieldValue(
                    value=year,
                    confidence=fields.date.confidence,
                    source=fields.date.source,
                    extraction_method="year_from_date",
                )

        # ── Report ID extraction ────────────────────────────────────────
        fields.report_id = extract_report_id(text, metadata)

        # ── Document type classification ────────────────────────────────
        fields.document_type = classify_document_type(text)

        # ── Maritime-specific classification ────────────────────────────
        (fields.maritime_document_type,
         fields.maritime_domain,
         fields.maritime_subdomain) = classify_maritime_document(text, metadata)

        # ── Store results ───────────────────────────────────────────────
        record.heuristic_fields = fields
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        logger.debug(
            "  Heuristic results: title=%s (%.2f), author=%s (%.2f), "
            "org=%s (%.2f), date=%s (%.2f), type=%s — %d ms",
            fields.title.value is not None, fields.title.confidence,
            fields.author.value is not None, fields.author.confidence,
            fields.organization.value, fields.organization.confidence,
            fields.date.value, fields.date.confidence,
            fields.maritime_document_type.value,
            elapsed_ms,
        )

    def _extract_title(self, text: str, metadata: dict, pdf_path: str) -> FieldValue:
        """Extract the document title using multiple strategies.

        Strategy priority:
          1. Largest font text on page 1 (highest confidence)
          2. PDF metadata /Title (if not garbage)
          3. Regex patterns ("Title:", "Report:", etc.)
          4. First significant non-boilerplate line

        Args:
            text:     Embedded text from first pages.
            metadata: PDF Info dictionary.
            pdf_path: Path to PDF (for font analysis).

        Returns:
            FieldValue with the best title candidate.
        """
        candidates: list[FieldValue] = []

        # ── Strategy 1: Largest font on page 1 ─────────────────────────
        try:
            doc = fitz.open(pdf_path)
            if len(doc) > 0:
                blocks = doc[0].get_text("dict")["blocks"]
                max_size = 0.0
                max_text = ""

                for block in blocks:
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if span["size"] > max_size and len(span["text"].strip()) > 5:
                                max_size = span["size"]
                                max_text = span["text"].strip()

                if max_size > 14 and max_text and not _is_boilerplate(max_text):
                    candidates.append(FieldValue(
                        value=max_text,
                        confidence=0.80,
                        source="heuristic",
                        extraction_method="largest_font_page1",
                    ))
            doc.close()
        except Exception:
            pass  # Font analysis is best-effort

        # ── Strategy 2: PDF metadata /Title ─────────────────────────────
        title_meta = metadata.get("title", "")
        if title_meta and len(title_meta) > 5 and not _is_garbage_title(title_meta):
            candidates.append(FieldValue(
                value=title_meta.strip(),
                confidence=0.65,
                source="metadata",
                extraction_method="pdf_info_title",
            ))

        # ── Strategy 3: Regex patterns ──────────────────────────────────
        if text:
            patterns = [
                (r'(?:Title|TITLE)[:\s]+(.{10,150})', 0.75),
                (r'^(?:Report|Paper|Article)[:\s]+(.{10,150})', 0.60),
                (r'^(?:Technical\s+(?:Report|Note|Memo))[:\s]+(.{10,150})', 0.65),
            ]
            for pattern, conf in patterns:
                match = re.search(pattern, text[:3000], re.MULTILINE)
                if match:
                    title_text = match.group(1).strip()
                    if not _is_boilerplate(title_text):
                        candidates.append(FieldValue(
                            value=title_text,
                            confidence=conf,
                            source="heuristic",
                            extraction_method=f"regex:title_label",
                        ))

        # ── Strategy 4: First significant line ──────────────────────────
        if text:
            lines = text.strip().split('\n')
            for line in lines[:20]:
                line = line.strip()
                if 10 < len(line) < 200 and not _is_boilerplate(line):
                    candidates.append(FieldValue(
                        value=line,
                        confidence=0.35,
                        source="heuristic",
                        extraction_method="first_significant_line",
                    ))
                    break

        if candidates:
            return max(candidates, key=lambda c: c.confidence)

        return FieldValue(value=None, confidence=0.0, source="heuristic",
                          extraction_method="no_title_found")


# =============================================================================
# Helper Functions
# =============================================================================

def _is_garbage_title(title: str) -> bool:
    """Check if a title is auto-generated garbage."""
    lower = title.lower().strip()
    garbage = [
        r'^untitled', r'\.pdf$', r'\.doc[x]?$', r'^microsoft\s+word',
        r'^slide\s+\d+', r'^page\s+\d+', r'^document\d*$', r'^\d+$',
        r'^scan', r'^img[_\-]', r'^copy\s+of',
    ]
    return any(re.search(p, lower) for p in garbage)


def _is_boilerplate(text: str) -> bool:
    """Check if text is common boilerplate (headers, footers, etc.)."""
    lower = text.lower().strip()
    boilerplate = [
        "confidential", "proprietary", "all rights reserved",
        "page ", "table of contents", "list of figures",
        "list of tables", "revision history", "document control",
        "this page intentionally", "copyright", "disclaimer",
    ]
    return any(bp in lower for bp in boilerplate) or len(lower) < 5
