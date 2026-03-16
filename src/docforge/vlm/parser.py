"""
DocForge — VLM Response Parser
================================

Parses JSON responses from Vision-Language Models into ExtractedFields.
Handles common VLM output quirks:
  - Markdown code fences around JSON
  - Trailing commas
  - Nested JSON objects within text
  - Non-JSON responses (falls back to regex extraction)
"""

from __future__ import annotations

import json
import re
from typing import Optional

from docforge.extractors.patterns.dates import extract_year
from docforge.infra.logging import get_logger
from docforge.models.fields import ExtractedFields, FieldValue

logger = get_logger(__name__)


def parse_vlm_response(raw: str, model_name: str) -> ExtractedFields:
    """Parse a VLM JSON response into ExtractedFields.

    Handles multiple formats that VLMs may return:
      1. Clean JSON object
      2. JSON wrapped in markdown code fences
      3. JSON embedded in explanatory text
      4. Malformed JSON with trailing commas

    Args:
        raw:        Raw response text from the VLM.
        model_name: Name of the model (for extraction_method tagging).

    Returns:
        ExtractedFields populated from the VLM response.
    """
    source_tag = f"vlm:{model_name}"

    # ── Attempt 1: Direct JSON parse ────────────────────────────────────
    data = _try_parse_json(raw)

    # ── Attempt 2: Strip markdown code fences ───────────────────────────
    if data is None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (with optional language tag)
            cleaned = re.sub(r'^```\w*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            data = _try_parse_json(cleaned)

    # ── Attempt 3: Extract JSON object with regex ───────────────────────
    if data is None:
        # Find the first {...} block (handles nested braces simply)
        match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
        if match:
            data = _try_parse_json(match.group())

    # ── Failed: return empty fields ─────────────────────────────────────
    if data is None:
        logger.warning("VLM response could not be parsed as JSON — returning empty fields")
        logger.debug("  Raw response (first 500 chars): %s", raw[:500])
        return _empty_vlm_fields(source_tag, "vlm_parse_error")

    # ── Convert parsed data to ExtractedFields ──────────────────────────
    return _data_to_fields(data, source_tag)


def _try_parse_json(text: str) -> Optional[dict]:
    """Attempt to parse text as JSON, handling common VLM quirks."""
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try fixing trailing commas (common VLM issue)
        try:
            fixed = re.sub(r',\s*}', '}', text)
            fixed = re.sub(r',\s*]', ']', fixed)
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None


def _data_to_fields(data: dict, source_tag: str) -> ExtractedFields:
    """Convert a parsed JSON dict to ExtractedFields with confidence scores.

    VLM base confidence levels:
      - title:    0.85 (VLMs are good at identifying main titles)
      - author:   0.80
      - org:      0.80
      - date:     0.85 (VLMs read dates well from images)
      - report_id: 0.90 (when present, usually very accurate)
      - doc_type: 0.80
      - summary:  0.75

    Args:
        data:       Parsed JSON dictionary from VLM response.
        source_tag: Source identifier (e.g., "vlm:minicpm-v").

    Returns:
        Populated ExtractedFields.
    """
    fields = ExtractedFields()

    # Helper: create a FieldValue from a JSON key
    def fv(key: str, base_conf: float) -> FieldValue:
        val = data.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            return FieldValue(value=None, confidence=0.0,
                              source="vlm", extraction_method=source_tag)
        return FieldValue(value=str(val).strip(), confidence=base_conf,
                          source="vlm", extraction_method=source_tag)

    fields.title = fv("title", 0.85)
    fields.author = fv("author", 0.80)
    fields.organization = fv("organization", 0.80)
    fields.date = fv("date", 0.85)
    fields.report_id = fv("report_id", 0.90)
    fields.document_type = fv("document_type", 0.80)
    fields.summary = fv("summary", 0.75)

    # Optional fields (may not be present in all responses)
    fields.vessel_name = fv("vessel_name", 0.80)
    fields.equipment_name = fv("equipment_name", 0.80)

    # Year from date
    date_val = data.get("date")
    if date_val:
        year = extract_year(str(date_val))
        if year:
            fields.year = FieldValue(
                value=year, confidence=0.85,
                source="vlm", extraction_method=source_tag,
            )

    # Keywords (comma-separated string or list)
    kw_raw = data.get("keywords", "")
    if isinstance(kw_raw, list):
        keywords = [str(k).strip() for k in kw_raw if k]
    elif isinstance(kw_raw, str):
        keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
    else:
        keywords = []

    fields.keywords = [
        FieldValue(value=kw, confidence=0.70,
                   source="vlm", extraction_method=source_tag)
        for kw in keywords[:10]
    ]

    return fields


def _empty_vlm_fields(source_tag: str, reason: str) -> ExtractedFields:
    """Create empty ExtractedFields for VLM parse failure."""
    fields = ExtractedFields()
    # All fields remain at default (empty FieldValue)
    return fields
