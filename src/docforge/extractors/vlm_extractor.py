"""
DocForge — Stage 3 Path A: VLM Extractor
==========================================

Sends rendered page images to a Vision-Language Model for:
  1. Direct filename generation (primary mode)
  2. Structured metadata extraction (when needed)

Includes:
  - Smart page selection (page 2 fallback if page 1 has no title)
  - Diagram detection heuristic
  - Timeout and error handling with graceful degradation
"""

from __future__ import annotations

import re
import time

from docforge.infra.logging import get_logger
from docforge.vlm.manager import ModelManager
from docforge.vlm.parser import parse_vlm_response
from docforge.vlm.prompts import build_vlm_prompt

logger = get_logger(__name__)


class VLMExtractor:
    """Stage 3 Path A: Extract metadata via Vision-Language Model."""

    def __init__(self, model_manager: ModelManager):
        self.models = model_manager

    def generate_filename(self, page_images: list[str], record) -> str:
        """Ask the VLM to directly generate a descriptive filename.

        Args:
            page_images: List of paths to rendered PNG images.
            record:      DocumentRecord for context.

        Returns:
            Suggested filename (without extension), or empty string on failure.
        """
        if not page_images:
            return ""

        prompt = build_vlm_prompt(record)

        try:
            raw = self.models.complete_with_image(
                image_path=page_images[0],
                prompt=prompt,
            )
        except (TimeoutError, RuntimeError) as exc:
            logger.warning("VLM filename gen failed for %s: %s", record.file_id[:12], exc)
            return ""

        # Clean up VLM response — extract just the filename
        name = self._clean_filename_response(raw)
        record.vlm_raw_response = raw
        record.vlm_model_used = self.models.config.model

        logger.debug("  VLM suggested name: '%s'", name)
        return name

    def extract(self, page_images: list[str], record) -> None:
        """Send page images to the VLM and populate record.vlm_fields.

        Args:
            page_images: List of paths to rendered PNG images.
            record:      DocumentRecord to populate.
        """
        if not page_images:
            logger.warning("No page images available for VLM extraction")
            return

        start = time.perf_counter()
        model_name = self.models.config.model

        logger.debug("Stage 3 (VLM) — Extracting: %s", record.file_id[:12])

        # Detect diagram mode (very little text on page 1)
        is_diagram = record.text_quality_score < 0.1

        # Build prompt
        from docforge.vlm.prompts import build_extraction_prompt
        prompt = build_extraction_prompt(record)

        # Send page 1 to VLM
        try:
            raw_response = self.models.complete_with_image(
                image_path=page_images[0],
                prompt=prompt,
            )
        except (TimeoutError, RuntimeError) as exc:
            logger.warning("VLM inference failed for %s: %s", record.file_id[:12], exc)
            record.error_message = f"VLM error: {exc}"
            return

        # Parse response
        fields = parse_vlm_response(raw_response, model_name)
        record.vlm_raw_response = raw_response

        # Try page 2 if title not found
        if fields.title.is_empty() and len(page_images) > 1:
            logger.debug("  Title not found on page 1, trying page 2...")
            try:
                raw_p2 = self.models.complete_with_image(
                    image_path=page_images[1],
                    prompt=prompt,
                )
                fields_p2 = parse_vlm_response(raw_p2, model_name)
                fields = _merge_page_results(fields, fields_p2)
            except (TimeoutError, RuntimeError) as exc:
                logger.debug("  Page 2 VLM failed: %s", exc)

        # Store results
        record.vlm_fields = fields
        record.vlm_model_used = model_name

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.debug(
            "  VLM results: title=%s (%.2f), org=%s (%.2f) — %d ms",
            fields.title.value is not None, fields.title.confidence,
            fields.organization.value is not None, fields.organization.confidence,
            elapsed_ms,
        )

    @staticmethod
    def _clean_filename_response(raw: str) -> str:
        """Clean up a VLM response that should contain just a filename.

        Handles common VLM quirks: extra text, quotes, extensions, markdown,
        and mashed-together words without underscores.
        """
        text = raw.strip()

        # Remove markdown fences
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)

        # Take just the first line (VLMs sometimes add explanations)
        text = text.split('\n')[0].strip()

        # Remove "FILENAME:" prefix if echoed back
        text = re.sub(r'^(?:FILENAME|filename)[:\s]*', '', text).strip()

        # Remove quotes
        text = text.strip('"\'`')

        # Remove .pdf extension if included
        text = re.sub(r'\.pdf$', '', text, flags=re.IGNORECASE)

        # Replace spaces and hyphens with underscores
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        text = re.sub(r'[\s\-]+', '_', text)

        # Split camelCase / mashed words (e.g., "srihariOption" → "srihari_Option")
        text = re.sub(r'([a-z])([A-Z])', r'\1_\2', text)

        # Detect mashed-together lowercase without underscores (>25 chars with no _)
        # Split on common word boundaries
        if '_' not in text and len(text) > 25:
            # Try to split on common filename words
            text = re.sub(
                r'(report|certificate|invoice|letter|agreement|contract|card|'
                r'license|licence|offer|appointment|internship|project|'
                r'analysis|simulation|resume|marks|list|slip|degree|'
                r'completion|experience|training|course|exam)',
                r'_\1_', text, flags=re.IGNORECASE,
            )

        # Collapse multiple underscores
        text = re.sub(r'_+', '_', text)

        # Lowercase and trim
        text = text.lower().strip('_')

        # Remove redundant acronyms (e.g., "ceaa_corteva_electronic_access_agreement")
        parts = text.split('_')
        if len(parts) > 3:
            cleaned_parts = []
            for i, part in enumerate(parts):
                # Skip short all-alpha tokens (2-5 chars) that look like acronyms
                # if the following words start with the same letters
                if 2 <= len(part) <= 5 and part.isalpha():
                    remaining = parts[i + 1:i + 1 + len(part)]
                    if len(remaining) == len(part):
                        initials = ''.join(w[0] for w in remaining if w)
                        if initials == part:
                            continue  # Skip redundant acronym
                cleaned_parts.append(part)
            text = '_'.join(cleaned_parts)

        # Remove filler words
        filler = {'new', 'copy', 'final', 'draft', 'english', 'original', 'untitled'}
        parts = [p for p in text.split('_') if p not in filler]
        text = '_'.join(parts)

        # Enforce max length (break at word boundary)
        if len(text) > 60:
            text = text[:60].rsplit('_', 1)[0]

        return text


def _merge_page_results(page1, page2):
    """Merge results from two pages, preferring page 1 but filling gaps."""
    from docforge.models.fields import ALL_FIELD_NAMES, FieldValue

    for field_name in ALL_FIELD_NAMES:
        val1 = getattr(page1, field_name, FieldValue())
        val2 = getattr(page2, field_name, FieldValue())

        if val1.is_empty() and not val2.is_empty():
            val2_adjusted = FieldValue(
                value=val2.value,
                confidence=val2.confidence * 0.90,
                source=val2.source,
                extraction_method=f"{val2.extraction_method}:page2",
            )
            setattr(page1, field_name, val2_adjusted)

    return page1
