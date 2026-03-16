"""
DocForge — Folder Organisation Strategies
============================================

Maps documents to folder paths based on their metadata.
Strategies: year, type, year_type, domain_type, domain_year.

Folder structure example (domain_type):
    organized/
    ├── academic/
    │   ├── certificates/
    │   └── transcripts/
    ├── employment/
    │   ├── offer_letters/
    │   └── contracts/
    ├── financial/
    │   └── invoices/
    ├── identity/
    │   └── id_cards/
    └── general/
        └── other/
"""

from __future__ import annotations

from docforge.models.fields import ExtractedFields
from docforge.naming.sanitizer import sanitise_filename


# =============================================================================
# Strategy Functions
# =============================================================================

def strategy_year(fields: ExtractedFields) -> str:
    """Organise by year: 2023/"""
    year = fields.year.value if not fields.year.is_empty() else "unknown_year"
    return f"{year}/"


def strategy_type(fields: ExtractedFields) -> str:
    """Organise by document type: invoices/"""
    dtype = fields.document_type.value if not fields.document_type.is_empty() else "uncategorised"
    return f"{sanitise_filename(dtype, lowercase=False)}/"


def strategy_year_type(fields: ExtractedFields) -> str:
    """Organise by year then type: 2023/invoices/"""
    year = fields.year.value if not fields.year.is_empty() else "unknown_year"
    dtype = fields.document_type.value if not fields.document_type.is_empty() else "uncategorised"
    return f"{year}/{sanitise_filename(dtype, lowercase=False)}/"


def strategy_domain_type(fields: ExtractedFields) -> str:
    """Organise by broad domain then document type.

    Infers a broad domain category from the document type field:
        academic/certificates/
        employment/contracts/
        financial/invoices/
        identity/id_cards/

    Returns:
        Relative path string ending with '/'.
    """
    dtype = ""
    if not fields.document_type.is_empty():
        dtype = str(fields.document_type.value).lower()

    domain = _infer_domain(dtype)
    type_label = sanitise_filename(dtype, lowercase=False) if dtype else "other"

    return f"{domain}/{type_label}/"


def strategy_domain_year(fields: ExtractedFields) -> str:
    """Like domain_type but with year as final level.

    Example: academic/certificates/2023/
    """
    base = strategy_domain_type(fields)
    year = fields.year.value if not fields.year.is_empty() else "unknown_year"
    return f"{base}{year}/"


# =============================================================================
# Domain Inference
# =============================================================================

_DOMAIN_MAP = {
    "academic": [
        "certificate", "academic_transcript", "transcript", "marksheet",
        "degree", "diploma", "thesis", "research_paper", "conference_paper",
        "project_report",
    ],
    "employment": [
        "offer_letter", "appointment_letter", "experience_letter",
        "internship", "contract", "agreement", "nda",
    ],
    "financial": [
        "invoice", "receipt", "payslip", "tax", "bank_statement",
    ],
    "identity": [
        "id_card", "license", "passport", "visa", "voter_id", "aadhar", "pan",
    ],
    "technical": [
        "manual", "datasheet", "specification", "drawing", "diagram",
        "report", "technical_report",
    ],
    "correspondence": [
        "letter", "correspondence", "meeting_minutes", "presentation",
    ],
}


def _infer_domain(doc_type: str) -> str:
    """Map a document type to a broad domain folder."""
    doc_type_lower = doc_type.lower().strip()
    for domain, types in _DOMAIN_MAP.items():
        for t in types:
            if t in doc_type_lower or doc_type_lower in t:
                return domain
    return "general"


# =============================================================================
# Strategy Registry
# =============================================================================

STRATEGY_REGISTRY: dict[str, callable] = {
    "year": strategy_year,
    "type": strategy_type,
    "year_type": strategy_year_type,
    "domain_type": strategy_domain_type,
    "domain_year": strategy_domain_year,
}


def get_strategy(name: str):
    """Get a strategy function by name.

    Args:
        name: Strategy name from STRATEGY_REGISTRY.

    Returns:
        Strategy function that takes ExtractedFields and returns a path string.

    Raises:
        ValueError: If strategy name is unknown.
    """
    if name not in STRATEGY_REGISTRY:
        available = ", ".join(STRATEGY_REGISTRY.keys())
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
    return STRATEGY_REGISTRY[name]
