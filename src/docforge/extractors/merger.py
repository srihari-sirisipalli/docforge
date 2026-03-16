"""
DocForge — Stage 4: Field Merger
==================================

Merges extracted fields from multiple sources (metadata, VLM, heuristic)
into a single reconciled set using confidence-weighted selection.

When multiple sources agree on a field value, confidence is boosted
(cross-validation). When they disagree, the highest-confidence source wins.

This stage produces the final merged_fields that the name generator consumes.
"""

from __future__ import annotations

import re
import time

from docforge.infra.logging import get_logger
from docforge.models.fields import (
    ALL_FIELD_NAMES,
    ExtractedFields,
    FieldValue,
    empty_fields,
)

logger = get_logger(__name__)

# Cross-validation bonus: when two sources agree, boost by this amount
CROSS_VALIDATION_BOOST = 0.10

# Maximum allowed confidence (prevents overconfidence)
MAX_CONFIDENCE = 0.98


class FieldMerger:
    """Stage 4: Merge fields from all extraction sources.

    Takes metadata_fields, vlm_fields, and heuristic_fields from the
    DocumentRecord and produces a single merged_fields result.
    """

    def process(self, record) -> None:
        """Merge all available extracted fields into record.merged_fields.

        Args:
            record: DocumentRecord with metadata_fields and optionally
                    vlm_fields and/or heuristic_fields populated.
        """
        start = time.perf_counter()

        logger.debug("Stage 4 — Field merger: %s", record.file_id[:12])

        record.merged_fields = merge_fields(
            metadata_f=record.metadata_fields,
            vlm_f=record.vlm_fields,
            heuristic_f=record.heuristic_fields,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Log the merge result summary
        merged = record.merged_fields
        filled = sum(
            1 for name in ALL_FIELD_NAMES
            if not getattr(merged, name, FieldValue()).is_empty()
        )
        logger.debug(
            "  Merged: %d / %d fields filled — %d ms",
            filled, len(ALL_FIELD_NAMES), elapsed_ms,
        )


def merge_fields(
    metadata_f: ExtractedFields,
    vlm_f: ExtractedFields | None,
    heuristic_f: ExtractedFields | None,
) -> ExtractedFields:
    """Merge fields from all sources using confidence-weighted selection.

    For each field:
      1. Collect all non-empty candidates from available sources
      2. Sort by confidence (highest first)
      3. If top-2 candidates agree (normalised values match), boost confidence
      4. Select the highest-confidence value

    Args:
        metadata_f:  Fields from PDF metadata (Stage 1).
        vlm_f:       Fields from VLM vision pass (Stage 3 Path A), or None.
        heuristic_f: Fields from heuristic extraction (Stage 3 Path B/C), or None.

    Returns:
        Merged ExtractedFields with the best value for each field.
    """
    merged = empty_fields()

    sources = [
        ("metadata", metadata_f),
        ("vlm", vlm_f),
        ("heuristic", heuristic_f),
    ]

    for field_name in ALL_FIELD_NAMES:
        candidates: list[FieldValue] = []

        for source_name, source in sources:
            if source is None:
                continue
            field_val = getattr(source, field_name, None)
            if field_val and isinstance(field_val, FieldValue) and not field_val.is_empty():
                candidates.append(field_val)

        if not candidates:
            # No source has this field — leave as empty
            setattr(merged, field_name, FieldValue(
                value=None, confidence=0.0, source="none",
                extraction_method="no_candidates",
            ))
            continue

        # Sort by confidence (highest first)
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        best = candidates[0]

        # Cross-validate: if top two sources agree, boost confidence
        if len(candidates) >= 2:
            val1 = _normalise_for_comparison(best.value)
            val2 = _normalise_for_comparison(candidates[1].value)

            if val1 and val2 and val1 == val2:
                boosted_conf = min(best.confidence + CROSS_VALIDATION_BOOST, MAX_CONFIDENCE)
                best = FieldValue(
                    value=best.value,
                    confidence=boosted_conf,
                    source=f"{best.source}+cross_validated",
                    extraction_method=best.extraction_method,
                )

        setattr(merged, field_name, best)

    # Handle keywords separately (list field)
    merged.keywords = _merge_keywords(metadata_f, vlm_f, heuristic_f)

    return merged


def _merge_keywords(
    metadata_f: ExtractedFields,
    vlm_f: ExtractedFields | None,
    heuristic_f: ExtractedFields | None,
) -> list[FieldValue]:
    """Merge keyword lists from all sources, deduplicating by value."""
    seen: set[str] = set()
    merged_kw: list[FieldValue] = []

    for source in [vlm_f, heuristic_f, metadata_f]:
        if source is None:
            continue
        for kw in source.keywords:
            if kw.value and kw.value.lower() not in seen:
                seen.add(kw.value.lower())
                merged_kw.append(kw)

    # Sort by confidence and cap at 10
    merged_kw.sort(key=lambda k: k.confidence, reverse=True)
    return merged_kw[:10]


def _normalise_for_comparison(value) -> str:
    """Normalise a field value for cross-validation comparison.

    Strips whitespace, lowercases, removes punctuation, and collapses
    multiple spaces. This allows fuzzy matching between sources.

    Args:
        value: The field value to normalise.

    Returns:
        Normalised string for comparison.
    """
    if value is None:
        return ""
    text = str(value).lower().strip()
    text = re.sub(r'[^\w\s]', '', text)   # Remove punctuation
    text = re.sub(r'\s+', ' ', text)       # Collapse whitespace
    return text
