"""
DocForge — Stage 5: Filename Generator
========================================

Produces deterministic canonical filenames from merged fields.
Auto-selects the naming template based on the document's maritime type,
then fills template variables, sanitises, and enforces length limits.

Determinism guarantee: the same merged_fields always produce the same
filename, regardless of processing order or parallelism.

Template selection:
  1. Look up MaritimeDocumentType in TEMPLATE_REGISTRY
  2. Fall back to user-configured default_template
  3. Fill template variables from merged_fields
  4. Skip empty variables (don't produce "___" gaps)
  5. Sanitise and enforce max_length
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from docforge.extractors.patterns.authors import extract_author_last_name
from docforge.infra.config import NamingConfig
from docforge.infra.logging import get_logger
from docforge.models.fields import ExtractedFields
from docforge.naming.sanitizer import sanitise_filename
from docforge.naming.templates import DEFAULT_TEMPLATE, get_template_for_type

logger = get_logger(__name__)


class FilenameGenerator:
    """Stage 5: Generate deterministic canonical filenames from extracted fields.

    Auto-selects the naming template based on the detected maritime document
    type, then fills variables and produces a clean, filesystem-safe filename.
    """

    def __init__(self, config: NamingConfig):
        self.config = config

    def process(self, record) -> None:
        """Generate the canonical filename and store on the record.

        Args:
            record: DocumentRecord with merged_fields populated.
        """
        start = time.perf_counter()
        fields = record.merged_fields

        # Select template based on maritime document type
        doc_type = fields.maritime_document_type.value
        if doc_type:
            template = get_template_for_type(doc_type)
        else:
            template = self.config.default_template or DEFAULT_TEMPLATE

        # Generate filename
        original_name = Path(record.original_path).stem if record.original_path else ""
        filename = self.generate(fields, record.file_id, template, original_name)
        record.canonical_name = filename
        record.current_stage = 5

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.debug(
            "Stage 5 — Name generated: '%s' (template=%s) — %d ms",
            filename, template, elapsed_ms,
        )

    def generate(
        self,
        fields: ExtractedFields,
        file_id: str,
        template: str | None = None,
        original_name: str = "",
    ) -> str:
        """Generate a filename from extracted fields.

        Args:
            fields:        Merged ExtractedFields.
            file_id:       Document identifier (used as fallback).
            template:      Override template (if None, auto-selects from doc type).
            original_name: Original filename (used as fallback context).

        Returns:
            Canonical filename with .pdf extension.
        """
        if template is None:
            doc_type = fields.maritime_document_type.value
            template = get_template_for_type(doc_type) if doc_type else DEFAULT_TEMPLATE

        # ── Build template variables ────────────────────────────────────
        variables = {
            "year": self._get_year(fields),
            "date": self._get_date(fields),
            "author_last": self._get_author_last(fields),
            "author_full": self._get_author_full(fields),
            "title_short": self._get_title_short(fields),
            "title_full": self._get_title_full(fields),
            "org": self._get_org(fields),
            "type": self._get_type(fields),
            "report_id": self._get_report_id(fields),
            "vessel": self._get_vessel(fields),
            "equipment": self._get_equipment(fields),
        }

        # ── Fill template ───────────────────────────────────────────────
        parts: list[str] = []
        for segment in self._parse_template(template):
            if segment.startswith("{") and segment.endswith("}"):
                key = segment[1:-1]
                value = variables.get(key, "")
                if value:
                    parts.append(value)
                # Empty variables are silently skipped (no gaps)
            else:
                parts.append(segment)

        # ── Fallback: if all parts are empty or separator-only
        meaningful = [p for p in parts if p.strip(self.config.separator).strip()]
        if not meaningful:
            if original_name:
                # Use cleaned original filename as fallback
                stem = re.sub(r'\.pdf$', '', original_name, flags=re.IGNORECASE)
                parts = [stem]
                logger.debug("  All fields empty — using original filename fallback")
            else:
                parts = [file_id[:12]]
                logger.debug("  All fields empty — using file_id fallback")

        # ── Assemble and sanitise ───────────────────────────────────────
        raw_name = self.config.separator.join(parts)
        filename = sanitise_filename(
            raw_name,
            separator=self.config.separator,
            lowercase=self.config.lowercase,
            strip_accents=self.config.strip_accents,
            max_length=self.config.max_length - 4,  # Reserve space for ".pdf"
        )

        return f"{filename}.pdf"

    # =====================================================================
    # Variable Extractors
    # =====================================================================

    def _get_year(self, fields: ExtractedFields) -> str:
        return str(fields.year.value) if not fields.year.is_empty() else ""

    def _get_date(self, fields: ExtractedFields) -> str:
        if fields.date.is_empty():
            return ""
        # Normalise date separators for filenames
        return str(fields.date.value).replace("-", "_").replace("/", "_")

    def _get_author_last(self, fields: ExtractedFields) -> str:
        if fields.author.is_empty():
            return ""
        return extract_author_last_name(str(fields.author.value))

    def _get_author_full(self, fields: ExtractedFields) -> str:
        return str(fields.author.value) if not fields.author.is_empty() else ""

    def _get_title_short(self, fields: ExtractedFields) -> str:
        if fields.title.is_empty():
            return ""
        # Take first 4 significant words (skip very short words)
        words = str(fields.title.value).split()
        significant = [w for w in words if len(w) > 2][:4]
        return self.config.separator.join(significant) if significant else ""

    def _get_title_full(self, fields: ExtractedFields) -> str:
        return str(fields.title.value) if not fields.title.is_empty() else ""

    def _get_org(self, fields: ExtractedFields) -> str:
        return str(fields.organization.value) if not fields.organization.is_empty() else ""

    def _get_type(self, fields: ExtractedFields) -> str:
        if not fields.maritime_document_type.is_empty():
            return str(fields.maritime_document_type.value).replace("_", " ")
        if not fields.document_type.is_empty():
            return str(fields.document_type.value)
        return ""

    def _get_report_id(self, fields: ExtractedFields) -> str:
        return str(fields.report_id.value) if not fields.report_id.is_empty() else ""

    def _get_vessel(self, fields: ExtractedFields) -> str:
        return str(fields.vessel_name.value) if not fields.vessel_name.is_empty() else ""

    def _get_equipment(self, fields: ExtractedFields) -> str:
        return str(fields.equipment_name.value) if not fields.equipment_name.is_empty() else ""

    @staticmethod
    def _parse_template(template: str) -> list[str]:
        """Parse a template string into segments.

        Splits on {variable} boundaries, returning alternating literal
        and variable segments.

        Args:
            template: Template string like "{org}_{title_short}_{year}".

        Returns:
            List of segments: ["{org}", "_", "{title_short}", "_", "{year}"]
        """
        segments: list[str] = []
        pattern = re.compile(r'(\{[^}]+\})')
        parts = pattern.split(template)
        for part in parts:
            if part:  # Skip empty strings from split
                segments.append(part)
        return segments
