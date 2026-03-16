"""
DocForge — Per-Type Naming Templates
======================================

The core domain-specific naming system. Each MaritimeDocumentType maps
to a naming template with the convention:

    ORGANISATION/AUTHOR FIRST, DATE/YEAR LAST

This ensures that browsing files sorted alphabetically groups documents
by their source organisation, while the trailing date makes versions
easy to distinguish.

Template variables:
    {org}           Organisation abbreviation (e.g., "DNV", "LR", "ABS")
    {author_last}   Author's last name
    {author_full}   Full author name
    {title_short}   First 4 significant words of the title
    {title_full}    Complete title (may be truncated by max_length)
    {report_id}     Document/report identifier
    {type}          Document type label
    {vessel}        Vessel or platform name
    {equipment}     Equipment name/model
    {date}          Full date (YYYY-MM-DD)
    {year}          Year only (YYYY)

Usage:
    from docforge.naming.templates import get_template_for_type
    template = get_template_for_type("class_rules")
    # Returns: "{org}_{title_short}_{report_id}_{year}"
"""

from __future__ import annotations

from docforge.models.enums import MaritimeDocumentType


# =============================================================================
# Per-Type Template Registry
# =============================================================================
# Convention: ORG/AUTHOR first, DATE/YEAR last.
#
# Templates are ordered so that the most distinctive fields come first,
# creating natural alphabetical groupings when files are sorted.

TEMPLATE_REGISTRY: dict[MaritimeDocumentType, str] = {

    # ── Classification Societies ─────────────────────────────────────────
    # Files group by society (DNV, LR, ABS...) then by title/rule reference
    MaritimeDocumentType.CLASS_RULES:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.CLASS_GUIDANCE:
        "{org}_{report_id}_{title_short}_{year}",

    MaritimeDocumentType.CLASS_CERTIFICATE:
        "{org}_{vessel}_{title_short}_{date}",

    MaritimeDocumentType.CLASS_NOTATION:
        "{org}_{title_short}_{year}",

    # ── Naval Architecture ───────────────────────────────────────────────
    # Files group by organisation/author then by analysis type
    MaritimeDocumentType.STABILITY_ANALYSIS:
        "{org}_{vessel}_{title_short}_{date}",

    MaritimeDocumentType.STRUCTURAL_ANALYSIS:
        "{org}_{author_last}_{title_short}_{year}",

    MaritimeDocumentType.HYDRODYNAMIC_ANALYSIS:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.LINES_PLAN:
        "{org}_{vessel}_{title_short}_{report_id}",

    MaritimeDocumentType.GENERAL_ARRANGEMENT:
        "{org}_{vessel}_{title_short}_{report_id}_{year}",

    # ── Marine Operations ────────────────────────────────────────────────
    MaritimeDocumentType.VOYAGE_PLAN:
        "{org}_{vessel}_{title_short}_{date}",

    MaritimeDocumentType.CARGO_PLAN:
        "{org}_{vessel}_{title_short}_{date}",

    MaritimeDocumentType.BALLAST_PLAN:
        "{org}_{vessel}_{title_short}_{year}",

    MaritimeDocumentType.SURVEY_REPORT:
        "{org}_{vessel}_{title_short}_{date}",

    MaritimeDocumentType.INSPECTION_REPORT:
        "{org}_{vessel}_{title_short}_{date}",

    MaritimeDocumentType.INCIDENT_REPORT:
        "{org}_{title_short}_{date}",

    MaritimeDocumentType.PROCEDURE_SOP:
        "{org}_{title_short}_{year}",

    # ── Offshore & Subsea ────────────────────────────────────────────────
    MaritimeDocumentType.PIPELINE_DESIGN:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.RISER_ANALYSIS:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.MOORING_ANALYSIS:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.FEA_REPORT:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.CFD_REPORT:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.INSTALLATION_REPORT:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.FEED_STUDY:
        "{org}_{title_short}_{year}",

    # ── Equipment Manuals ────────────────────────────────────────────────
    # Group by manufacturer then by equipment name
    MaritimeDocumentType.ENGINE_MANUAL:
        "{org}_{equipment}_{title_short}_{year}",

    MaritimeDocumentType.EQUIPMENT_MANUAL:
        "{org}_{equipment}_{title_short}_{year}",

    MaritimeDocumentType.NAVIGATION_MANUAL:
        "{org}_{equipment}_{title_short}_{year}",

    MaritimeDocumentType.ELECTRICAL_MANUAL:
        "{org}_{title_short}_{year}",

    # ── Regulatory ───────────────────────────────────────────────────────
    MaritimeDocumentType.IMO_DOCUMENT:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.FLAG_STATE_DOCUMENT:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.PORT_STATE_DOCUMENT:
        "{org}_{title_short}_{year}",

    MaritimeDocumentType.ISM_ISPS:
        "{org}_{title_short}_{year}",

    # ── Research ─────────────────────────────────────────────────────────
    # Research papers: author first (academic convention)
    MaritimeDocumentType.RESEARCH_PAPER:
        "{author_last}_{title_short}_{year}",

    MaritimeDocumentType.THESIS:
        "{author_last}_{title_short}_{org}_{year}",

    MaritimeDocumentType.CONFERENCE_PAPER:
        "{author_last}_{title_short}_{org}_{year}",

    # ── Commercial ───────────────────────────────────────────────────────
    MaritimeDocumentType.CONTRACT:
        "{org}_{title_short}_{date}",

    MaritimeDocumentType.INVOICE:
        "{org}_{report_id}_{date}",

    MaritimeDocumentType.PROPOSAL:
        "{org}_{title_short}_{date}",

    MaritimeDocumentType.CORRESPONDENCE:
        "{org}_{author_last}_{title_short}_{date}",

    MaritimeDocumentType.MEETING_MINUTES:
        "{org}_{title_short}_{date}",

    # ── General ──────────────────────────────────────────────────────────
    MaritimeDocumentType.TECHNICAL_REPORT:
        "{org}_{author_last}_{title_short}_{year}",

    MaritimeDocumentType.DATASHEET:
        "{org}_{title_short}_{report_id}",

    MaritimeDocumentType.SPECIFICATION:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.DRAWING:
        "{org}_{title_short}_{report_id}_{year}",

    MaritimeDocumentType.PRESENTATION:
        "{author_last}_{org}_{title_short}_{year}",

    MaritimeDocumentType.OTHER:
        "{org}_{title_short}_{year}",
}

# Default template used when document type is unknown or not in registry
DEFAULT_TEMPLATE = "{type}_{org}_{title_short}_{year}"


def get_template_for_type(doc_type: str | MaritimeDocumentType) -> str:
    """Look up the naming template for a maritime document type.

    Args:
        doc_type: MaritimeDocumentType enum value or its string name.

    Returns:
        Template string with {variable} placeholders.

    Examples:
        >>> get_template_for_type("class_rules")
        '{org}_{title_short}_{report_id}_{year}'
        >>> get_template_for_type(MaritimeDocumentType.RESEARCH_PAPER)
        '{author_last}_{title_short}_{year}'
    """
    # Convert string to enum if needed
    if isinstance(doc_type, str):
        try:
            doc_type = MaritimeDocumentType(doc_type)
        except ValueError:
            return DEFAULT_TEMPLATE

    return TEMPLATE_REGISTRY.get(doc_type, DEFAULT_TEMPLATE)
