"""
DocForge — Extracted Field Data Structures
==========================================

Core data structures for representing extracted metadata fields.
Every field carries a value, a confidence score (0.0–1.0), a source tag,
and an extraction method identifier for full traceability.

These structures flow through the entire pipeline: extractors populate them,
the merger reconciles them, and the name generator consumes them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from docforge.models.enums import MaritimeDocumentType, MaritimeDomain


# =============================================================================
# FieldValue — Single extracted field with provenance
# =============================================================================

@dataclass
class FieldValue:
    """A single extracted metadata field with confidence and source tracking.

    Attributes:
        value:              The extracted value (str, date string, etc.), or None
                            if the field could not be determined.
        confidence:         Confidence score from 0.0 (no confidence) to 1.0
                            (absolute certainty). Used for merge priority.
        source:             Which extraction stage produced this value.
                            One of: "metadata", "heuristic", "vlm", "ocr", "none".
        extraction_method:  Specific method that found this value, for debugging.
                            E.g., "pdf_info_title", "regex:iso_date", "vlm:minicpm-v".
    """
    value: Any = None
    confidence: float = 0.0
    source: str = "none"
    extraction_method: str = "none"

    def is_empty(self) -> bool:
        """Return True if this field has no usable value."""
        return self.value is None or (isinstance(self.value, str) and not self.value.strip())

    def __repr__(self) -> str:
        if self.is_empty():
            return "FieldValue(empty)"
        return f"FieldValue({self.value!r}, conf={self.confidence:.2f}, src={self.source})"


# =============================================================================
# ExtractedFields — Complete set of fields for one document
# =============================================================================

@dataclass
class ExtractedFields:
    """Complete set of metadata fields extracted from a single document.

    Populated by extractors (metadata, VLM, heuristic, OCR) and merged by
    the FieldMerger into a final reconciled set.

    Maritime-specific fields (maritime_document_type, maritime_domain,
    maritime_subdomain) are populated by the heuristic and VLM extractors
    when maritime domain patterns are detected.
    """

    # --- Standard document fields ---
    title: FieldValue = field(default_factory=FieldValue)
    author: FieldValue = field(default_factory=FieldValue)
    organization: FieldValue = field(default_factory=FieldValue)
    report_id: FieldValue = field(default_factory=FieldValue)
    date: FieldValue = field(default_factory=FieldValue)
    year: FieldValue = field(default_factory=FieldValue)
    keywords: list[FieldValue] = field(default_factory=list)
    document_type: FieldValue = field(default_factory=FieldValue)
    language: FieldValue = field(default_factory=FieldValue)
    summary: FieldValue = field(default_factory=FieldValue)

    # --- Maritime domain-specific fields ---
    maritime_document_type: FieldValue = field(default_factory=FieldValue)
    """Specific maritime document type (e.g., 'class_rules', 'stability_analysis')."""

    maritime_domain: FieldValue = field(default_factory=FieldValue)
    """Top-level domain for folder routing (e.g., 'classification_societies')."""

    maritime_subdomain: FieldValue = field(default_factory=FieldValue)
    """Subdomain within the domain (e.g., 'DNV', 'stability', 'pipeline')."""

    vessel_name: FieldValue = field(default_factory=FieldValue)
    """Vessel or platform name if mentioned in the document."""

    equipment_name: FieldValue = field(default_factory=FieldValue)
    """Specific equipment referenced (e.g., 'Wartsila 12V46F')."""


# =============================================================================
# Field Name Registry
# =============================================================================

# List of all standard field names that participate in the merge process.
# Maritime-specific fields are merged separately.
STANDARD_FIELD_NAMES: list[str] = [
    "title", "author", "organization", "report_id",
    "date", "year", "document_type", "language", "summary",
]

MARITIME_FIELD_NAMES: list[str] = [
    "maritime_document_type", "maritime_domain", "maritime_subdomain",
    "vessel_name", "equipment_name",
]

ALL_FIELD_NAMES: list[str] = STANDARD_FIELD_NAMES + MARITIME_FIELD_NAMES


# =============================================================================
# Convenience Factories
# =============================================================================

def empty_field(source: str = "none") -> FieldValue:
    """Create an empty FieldValue with zero confidence."""
    return FieldValue(value=None, confidence=0.0, source=source, extraction_method="none")


def empty_fields() -> ExtractedFields:
    """Create an ExtractedFields instance with all fields empty."""
    return ExtractedFields()
