"""
DocForge — Stage 1: PDF Metadata Extractor
============================================

Reads the PDF Info dictionary and XMP metadata using PyMuPDF.
Extracts /Title, /Author, /Subject, /Keywords, /CreationDate, /ModDate,
/Producer and converts them into FieldValues.

Also computes the file_id (SHA-256 of first 64KB + file size) used
for deduplication and state tracking.

This is the fastest extraction stage (~5 ms per document).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import fitz  # PyMuPDF

from docforge.extractors.patterns.dates import extract_date, extract_year
from docforge.infra.logging import get_logger
from docforge.models.fields import ExtractedFields, FieldValue

logger = get_logger(__name__)


class MetadataExtractor:
    """Stage 1: Extract metadata from PDF Info dictionary.

    Reads built-in PDF metadata fields and converts them to FieldValues
    with appropriate confidence scores. PDF metadata is generally low
    confidence (often auto-generated or empty), but provides useful
    signals for cross-validation with VLM/heuristic results.
    """

    def process(self, record) -> None:
        """Extract PDF metadata and populate record fields in-place.

        Args:
            record: DocumentRecord to populate. Must have original_path set.
        """
        path = record.original_path
        logger.debug("Stage 1 — Metadata extraction: %s", Path(path).name)

        try:
            doc = fitz.open(path)
        except Exception as exc:
            logger.error("Cannot open PDF: %s — %s", path, exc)
            record.error_message = f"PDF open failed: {exc}"
            return

        try:
            # ── Raw metadata ────────────────────────────────────────────
            meta = doc.metadata or {}
            record.pdf_metadata = dict(meta)
            record.page_count = len(doc)

            # ── Convert to ExtractedFields ──────────────────────────────
            fields = ExtractedFields()

            # Title
            title = meta.get("title", "").strip()
            if title and not _is_garbage_title(title):
                fields.title = FieldValue(
                    value=title,
                    confidence=0.60,
                    source="metadata",
                    extraction_method="pdf_info_title",
                )

            # Author
            author = meta.get("author", "").strip()
            if author and len(author) > 2:
                fields.author = FieldValue(
                    value=author,
                    confidence=0.55,
                    source="metadata",
                    extraction_method="pdf_info_author",
                )

            # Subject → sometimes contains report ID or keywords
            subject = meta.get("subject", "").strip()
            if subject:
                fields.summary = FieldValue(
                    value=subject,
                    confidence=0.40,
                    source="metadata",
                    extraction_method="pdf_info_subject",
                )

            # Keywords
            keywords_raw = meta.get("keywords", "").strip()
            if keywords_raw:
                kw_list = [k.strip() for k in keywords_raw.split(",") if k.strip()]
                fields.keywords = [
                    FieldValue(value=kw, confidence=0.50, source="metadata",
                               extraction_method="pdf_info_keywords")
                    for kw in kw_list[:10]  # Cap at 10 keywords
                ]

            # Dates
            date_field = extract_date("", meta)
            if not date_field.is_empty():
                fields.date = date_field
                year = extract_year(date_field.value)
                if year:
                    fields.year = FieldValue(
                        value=year,
                        confidence=date_field.confidence,
                        source="metadata",
                        extraction_method="pdf_date_year",
                    )

            # Producer → sometimes reveals the creating software/org
            producer = meta.get("producer", "").strip()
            creator = meta.get("creator", "").strip()
            if producer or creator:
                # Store for potential org detection downstream
                pass

            record.metadata_fields = fields
            record.current_stage = 1

            logger.debug(
                "  Metadata extracted: title=%s, author=%s, pages=%d",
                bool(title), bool(author), record.page_count,
            )

        finally:
            doc.close()


def compute_file_id(path: str) -> str:
    """Compute a unique file identifier from file content and size.

    Uses SHA-256 of the first 64KB concatenated with the file size.
    This is fast (~1 ms) and collision-resistant for practical purposes.

    Args:
        path: Absolute path to the file.

    Returns:
        Hex-encoded hash string.
    """
    file_size = os.path.getsize(path)
    sha = hashlib.sha256()

    with open(path, "rb") as f:
        chunk = f.read(65536)  # First 64 KB
        sha.update(chunk)

    # Include file size to differentiate files with same first 64KB
    sha.update(str(file_size).encode("ascii"))

    return sha.hexdigest()


def _is_garbage_title(title: str) -> bool:
    """Check if a PDF metadata title is auto-generated garbage.

    Many PDFs have titles like 'Microsoft Word - document1.docx',
    'untitled', or just the filename.

    Args:
        title: The raw title string.

    Returns:
        True if the title is likely garbage.
    """
    import re
    lower = title.lower().strip()

    garbage_patterns = [
        r'^untitled',
        r'\.pdf$',
        r'\.doc[x]?$',
        r'\.xls[x]?$',
        r'^microsoft\s+word',
        r'^microsoft\s+excel',
        r'^microsoft\s+powerpoint',
        r'^slide\s+\d+',
        r'^page\s+\d+',
        r'^document\d*$',
        r'^\d+$',
        r'^scan',
        r'^img[_\-]',
        r'^dsc[_\-]',
        r'^copy\s+of',
    ]

    return any(re.search(p, lower) for p in garbage_patterns)
