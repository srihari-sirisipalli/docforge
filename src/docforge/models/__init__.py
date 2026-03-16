"""
DocForge — Data Models Package
===============================

Re-exports all core data structures for convenient access:

    from docforge.models import DocumentRecord, ExtractedFields, FieldValue
    from docforge.models import MaritimeDocumentType, ExtractionStrategy
"""

from docforge.models.enums import (
    DOCTYPE_TO_DOMAIN,
    KNOWN_MARITIME_ORGS,
    DocumentStatus,
    ErrorSeverity,
    ExtractionStrategy,
    MaritimeDocumentType,
    MaritimeDomain,
)
from docforge.models.fields import (
    ALL_FIELD_NAMES,
    MARITIME_FIELD_NAMES,
    STANDARD_FIELD_NAMES,
    ExtractedFields,
    FieldValue,
    empty_field,
    empty_fields,
)
from docforge.models.record import DocumentRecord, FileOp, PendingDocument

__all__ = [
    # Enums
    "ExtractionStrategy", "DocumentStatus", "ErrorSeverity",
    "MaritimeDocumentType", "MaritimeDomain",
    "DOCTYPE_TO_DOMAIN", "KNOWN_MARITIME_ORGS",
    # Fields
    "FieldValue", "ExtractedFields", "empty_field", "empty_fields",
    "STANDARD_FIELD_NAMES", "MARITIME_FIELD_NAMES", "ALL_FIELD_NAMES",
    # Records
    "DocumentRecord", "PendingDocument", "FileOp",
]
