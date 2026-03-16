"""
DocForge — Enumerations and Constants
======================================

Central definitions for all classification enums used across the system.
Includes both generic document types and domain-specific types for engineering, maritime, and offshore sectors.

These enums drive template selection, folder organisation, and extraction
strategy routing throughout the pipeline.
"""

from enum import Enum


# =============================================================================
# Pipeline Enums
# =============================================================================

class ExtractionStrategy(str, Enum):
    """Which extraction path the pipeline uses for a given document.

    Selected by the StrategyRouter based on hardware capabilities,
    document characteristics, and user configuration.
    """
    VLM_ONLY = "vlm_only"
    """VLM vision pass only — best for scanned/image PDFs."""

    VLM_PLUS_HEURISTIC = "vlm_plus_heuristic"
    """VLM + text heuristics for cross-validation — highest quality."""

    TEXT_HEURISTIC = "text_heuristic"
    """Embedded text + regex/rules — fast, no model needed."""

    OCR_HEURISTIC = "ocr_heuristic"
    """OCR on rendered images + heuristics — fallback for no-VLM systems."""

    METADATA_ONLY = "metadata_only"
    """PDF metadata dictionary only — emergency last resort."""


class DocumentStatus(str, Enum):
    """Processing status of a document in the pipeline."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"
    SKIPPED = "skipped"


class ErrorSeverity(str, Enum):
    """Severity classification for pipeline errors.

    Determines whether to retry, degrade, skip the document, or abort the job.
    """
    RECOVERABLE = "recoverable"
    """Retry may succeed (transient I/O error, temporary OOM)."""

    DEGRADED = "degraded"
    """Continue with reduced quality (VLM timeout → fall back to heuristic)."""

    FATAL_DOCUMENT = "fatal_doc"
    """Skip this document, continue the job (corrupt PDF, encrypted file)."""

    FATAL_JOB = "fatal_job"
    """Abort the entire job (disk full, drive disconnected)."""


# =============================================================================
# Maritime Domain Enums
# =============================================================================

class MaritimeDocumentType(str, Enum):
    """Domain-specific document types for the maritime and offshore industry.

    Each type maps to a specific naming template (org/author first, date/year
    last) and a folder location in the organised output structure.
    """

    # --- Classification Societies ---
    CLASS_RULES = "class_rules"
    """Classification society rules and regulations (e.g., DNV Rules for Ships)."""

    CLASS_GUIDANCE = "class_guidance"
    """Guidance notes, recommended practices (e.g., DNV-RP-C203)."""

    CLASS_CERTIFICATE = "class_certificate"
    """Survey certificates, type approval certificates, class notations."""

    CLASS_NOTATION = "class_notation"
    """Class notation descriptions, additional notations."""

    # --- Naval Architecture ---
    STABILITY_ANALYSIS = "stability_analysis"
    """Intact/damage stability calculations, stability booklets, GZ curves."""

    STRUCTURAL_ANALYSIS = "structural_analysis"
    """Midship section scantlings, hull girder strength, fatigue analysis."""

    HYDRODYNAMIC_ANALYSIS = "hydrodynamic_analysis"
    """Resistance/propulsion, seakeeping, manoeuvring studies."""

    LINES_PLAN = "lines_plan"
    """Hull form lines plans, body plans, waterline drawings."""

    GENERAL_ARRANGEMENT = "general_arrangement"
    """GA plans, deck layouts, compartment arrangements."""

    # --- Marine Operations ---
    VOYAGE_PLAN = "voyage_plan"
    """Voyage plans, passage planning documents."""

    CARGO_PLAN = "cargo_plan"
    """Cargo stowage plans, loading/discharge sequences, cargo manifests."""

    BALLAST_PLAN = "ballast_plan"
    """Ballast water management plans, exchange records."""

    SURVEY_REPORT = "survey_report"
    """Hull condition surveys, machinery surveys, class renewal surveys."""

    INSPECTION_REPORT = "inspection_report"
    """Port state inspections, flag state inspections, vetting inspections."""

    INCIDENT_REPORT = "incident_report"
    """Incident investigations, near-miss reports, accident analyses."""

    PROCEDURE_SOP = "procedure_sop"
    """Standard operating procedures, work instructions, checklists."""

    # --- Offshore & Subsea ---
    PIPELINE_DESIGN = "pipeline_design"
    """Pipeline design basis, routing studies, installation analyses."""

    RISER_ANALYSIS = "riser_analysis"
    """Riser configuration analysis, VIV studies, fatigue life assessment."""

    MOORING_ANALYSIS = "mooring_analysis"
    """Mooring system design, line tension analysis, anchor holding capacity."""

    FEA_REPORT = "fea_report"
    """Finite element analysis reports, stress analysis, buckling checks."""

    CFD_REPORT = "cfd_report"
    """Computational fluid dynamics reports, flow simulations."""

    INSTALLATION_REPORT = "installation_report"
    """Offshore installation procedures, lifting analysis, loadout reports."""

    FEED_STUDY = "feed_study"
    """Front-end engineering design studies, concept selection reports."""

    # --- Equipment ---
    ENGINE_MANUAL = "engine_manual"
    """Main engine, auxiliary engine operation/maintenance manuals."""

    EQUIPMENT_MANUAL = "equipment_manual"
    """General equipment manuals (pumps, compressors, HVAC, etc.)."""

    NAVIGATION_MANUAL = "navigation_manual"
    """Navigation equipment manuals (radar, ECDIS, AIS, gyro)."""

    ELECTRICAL_MANUAL = "electrical_manual"
    """Electrical systems, switchboard, generator manuals."""

    # --- Regulatory ---
    IMO_DOCUMENT = "imo_document"
    """IMO conventions, resolutions, circulars (SOLAS, MARPOL, STCW)."""

    FLAG_STATE_DOCUMENT = "flag_state_document"
    """Flag state circulars, marine guidance notes, statutory instruments."""

    PORT_STATE_DOCUMENT = "port_state_document"
    """Port state control guidelines, MoU documents."""

    ISM_ISPS = "ism_isps"
    """ISM Code, ISPS Code, safety management system documents."""

    # --- Research ---
    RESEARCH_PAPER = "research_paper"
    """Journal papers, conference papers, technical articles."""

    THESIS = "thesis"
    """Masters/PhD theses, dissertations."""

    CONFERENCE_PAPER = "conference_paper"
    """Conference proceedings (OMAE, ISOPE, RINA, SNAME)."""

    # --- Commercial ---
    CONTRACT = "contract"
    """Shipbuilding contracts, repair contracts, charter parties."""

    INVOICE = "invoice"
    """Invoices, payment requests, fee notes."""

    PROPOSAL = "proposal"
    """Proposals, quotations, tenders."""

    CORRESPONDENCE = "correspondence"
    """Letters, emails (saved as PDF), memos."""

    MEETING_MINUTES = "meeting_minutes"
    """Meeting minutes, progress meeting notes."""

    # --- General ---
    TECHNICAL_REPORT = "technical_report"
    """General technical reports not fitting other categories."""

    DATASHEET = "datasheet"
    """Equipment datasheets, product specification sheets."""

    SPECIFICATION = "specification"
    """Technical specifications, material specifications."""

    DRAWING = "drawing"
    """Technical drawings, diagrams, P&ID, schematics."""

    PRESENTATION = "presentation"
    """Slide decks, presentation materials."""

    OTHER = "other"
    """Documents that do not fit any defined category."""


class MaritimeDomain(str, Enum):
    """Top-level domain groupings for folder organisation.

    Each domain maps to a top-level folder in the organised output.
    """
    CLASSIFICATION_SOCIETIES = "classification_societies"
    NAVAL_ARCHITECTURE = "naval_architecture"
    MARINE_OPERATIONS = "marine_operations"
    OFFSHORE_SUBSEA = "offshore_subsea"
    EQUIPMENT = "equipment"
    REGULATORY = "regulatory"
    RESEARCH = "research"
    COMMERCIAL = "commercial"
    GENERAL = "general"


# =============================================================================
# Domain → Document Type Mapping
# =============================================================================

# Maps each MaritimeDocumentType to its parent domain for folder routing.
DOCTYPE_TO_DOMAIN: dict[MaritimeDocumentType, MaritimeDomain] = {
    # Classification
    MaritimeDocumentType.CLASS_RULES: MaritimeDomain.CLASSIFICATION_SOCIETIES,
    MaritimeDocumentType.CLASS_GUIDANCE: MaritimeDomain.CLASSIFICATION_SOCIETIES,
    MaritimeDocumentType.CLASS_CERTIFICATE: MaritimeDomain.CLASSIFICATION_SOCIETIES,
    MaritimeDocumentType.CLASS_NOTATION: MaritimeDomain.CLASSIFICATION_SOCIETIES,
    # Naval Architecture
    MaritimeDocumentType.STABILITY_ANALYSIS: MaritimeDomain.NAVAL_ARCHITECTURE,
    MaritimeDocumentType.STRUCTURAL_ANALYSIS: MaritimeDomain.NAVAL_ARCHITECTURE,
    MaritimeDocumentType.HYDRODYNAMIC_ANALYSIS: MaritimeDomain.NAVAL_ARCHITECTURE,
    MaritimeDocumentType.LINES_PLAN: MaritimeDomain.NAVAL_ARCHITECTURE,
    MaritimeDocumentType.GENERAL_ARRANGEMENT: MaritimeDomain.NAVAL_ARCHITECTURE,
    # Marine Operations
    MaritimeDocumentType.VOYAGE_PLAN: MaritimeDomain.MARINE_OPERATIONS,
    MaritimeDocumentType.CARGO_PLAN: MaritimeDomain.MARINE_OPERATIONS,
    MaritimeDocumentType.BALLAST_PLAN: MaritimeDomain.MARINE_OPERATIONS,
    MaritimeDocumentType.SURVEY_REPORT: MaritimeDomain.MARINE_OPERATIONS,
    MaritimeDocumentType.INSPECTION_REPORT: MaritimeDomain.MARINE_OPERATIONS,
    MaritimeDocumentType.INCIDENT_REPORT: MaritimeDomain.MARINE_OPERATIONS,
    MaritimeDocumentType.PROCEDURE_SOP: MaritimeDomain.MARINE_OPERATIONS,
    # Offshore & Subsea
    MaritimeDocumentType.PIPELINE_DESIGN: MaritimeDomain.OFFSHORE_SUBSEA,
    MaritimeDocumentType.RISER_ANALYSIS: MaritimeDomain.OFFSHORE_SUBSEA,
    MaritimeDocumentType.MOORING_ANALYSIS: MaritimeDomain.OFFSHORE_SUBSEA,
    MaritimeDocumentType.FEA_REPORT: MaritimeDomain.OFFSHORE_SUBSEA,
    MaritimeDocumentType.CFD_REPORT: MaritimeDomain.OFFSHORE_SUBSEA,
    MaritimeDocumentType.INSTALLATION_REPORT: MaritimeDomain.OFFSHORE_SUBSEA,
    MaritimeDocumentType.FEED_STUDY: MaritimeDomain.OFFSHORE_SUBSEA,
    # Equipment
    MaritimeDocumentType.ENGINE_MANUAL: MaritimeDomain.EQUIPMENT,
    MaritimeDocumentType.EQUIPMENT_MANUAL: MaritimeDomain.EQUIPMENT,
    MaritimeDocumentType.NAVIGATION_MANUAL: MaritimeDomain.EQUIPMENT,
    MaritimeDocumentType.ELECTRICAL_MANUAL: MaritimeDomain.EQUIPMENT,
    # Regulatory
    MaritimeDocumentType.IMO_DOCUMENT: MaritimeDomain.REGULATORY,
    MaritimeDocumentType.FLAG_STATE_DOCUMENT: MaritimeDomain.REGULATORY,
    MaritimeDocumentType.PORT_STATE_DOCUMENT: MaritimeDomain.REGULATORY,
    MaritimeDocumentType.ISM_ISPS: MaritimeDomain.REGULATORY,
    # Research
    MaritimeDocumentType.RESEARCH_PAPER: MaritimeDomain.RESEARCH,
    MaritimeDocumentType.THESIS: MaritimeDomain.RESEARCH,
    MaritimeDocumentType.CONFERENCE_PAPER: MaritimeDomain.RESEARCH,
    # Commercial
    MaritimeDocumentType.CONTRACT: MaritimeDomain.COMMERCIAL,
    MaritimeDocumentType.INVOICE: MaritimeDomain.COMMERCIAL,
    MaritimeDocumentType.PROPOSAL: MaritimeDomain.COMMERCIAL,
    MaritimeDocumentType.CORRESPONDENCE: MaritimeDomain.COMMERCIAL,
    MaritimeDocumentType.MEETING_MINUTES: MaritimeDomain.COMMERCIAL,
    # General
    MaritimeDocumentType.TECHNICAL_REPORT: MaritimeDomain.GENERAL,
    MaritimeDocumentType.DATASHEET: MaritimeDomain.GENERAL,
    MaritimeDocumentType.SPECIFICATION: MaritimeDomain.GENERAL,
    MaritimeDocumentType.DRAWING: MaritimeDomain.GENERAL,
    MaritimeDocumentType.PRESENTATION: MaritimeDomain.GENERAL,
    MaritimeDocumentType.OTHER: MaritimeDomain.GENERAL,
}


# =============================================================================
# Known Maritime Organisations
# =============================================================================

# Maps full names and common variations to canonical short abbreviations.
# Used by both heuristic extraction and VLM response normalisation.
KNOWN_MARITIME_ORGS: dict[str, str] = {
    # Classification Societies
    "det norske veritas": "DNV",
    "dnv": "DNV",
    "dnv gl": "DNV",
    "dnv-gl": "DNV",
    "germanischer lloyd": "DNV",
    "lloyd's register": "LR",
    "lloyds register": "LR",
    "lr": "LR",
    "american bureau of shipping": "ABS",
    "abs": "ABS",
    "bureau veritas": "BV",
    "bv": "BV",
    "registro italiano navale": "RINA",
    "rina": "RINA",
    "nippon kaiji kyokai": "NK",
    "classnk": "NK",
    "nk": "NK",
    "china classification society": "CCS",
    "ccs": "CCS",
    "korean register": "KR",
    "kr": "KR",
    "indian register of shipping": "IRS",
    "irs": "IRS",
    "iacs": "IACS",
    "russian maritime register": "RS",
    "rs": "RS",
    "polish register of shipping": "PRS",
    "prs": "PRS",
    "croatian register of shipping": "CRS",
    "crs": "CRS",
    "turkish lloyd": "TL",
    "tl": "TL",

    # Shipyards
    "hyundai heavy industries": "HHI",
    "hhi": "HHI",
    "samsung heavy industries": "SHI",
    "shi": "SHI",
    "daewoo shipbuilding": "DSME",
    "dsme": "DSME",
    "hanwha ocean": "Hanwha",

    # Engine Manufacturers
    "wartsila": "Wartsila",
    "wärtsilä": "Wartsila",
    "man energy solutions": "MAN",
    "man b&w": "MAN",
    "man": "MAN",
    "caterpillar": "CAT",
    "cat": "CAT",
    "rolls-royce": "RR",
    "rolls royce": "RR",
    "kongsberg": "Kongsberg",

    # Offshore / Subsea
    "subsea 7": "Subsea7",
    "subsea7": "Subsea7",
    "technipfmc": "TechnipFMC",
    "technip": "TechnipFMC",
    "saipem": "Saipem",
    "mcdermott": "McDermott",
    "wood group": "Wood",
    "aker solutions": "AkerSolutions",

    # Operators
    "maersk": "Maersk",
    "shell": "Shell",
    "bp": "BP",
    "totalenergies": "TotalEnergies",
    "total": "TotalEnergies",
    "equinor": "Equinor",
    "statoil": "Equinor",
    "petrobras": "Petrobras",
    "chevron": "Chevron",
    "exxonmobil": "ExxonMobil",

    # Research / Standards
    "imo": "IMO",
    "international maritime organization": "IMO",
    "marin": "MARIN",
    "sintef": "SINTEF",
    "nrel": "NREL",
    "nasa": "NASA",

    # Flag State Authorities
    "mca": "MCA",
    "maritime and coastguard agency": "MCA",
    "uscg": "USCG",
    "us coast guard": "USCG",
    "amsa": "AMSA",
    "australian maritime safety authority": "AMSA",
}
