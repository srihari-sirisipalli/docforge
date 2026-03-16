"""
DocForge — Report ID and Identifier Extraction
================================================

Extracts document identifiers: DOIs, ISBNs, arXiv IDs, report numbers,
and maritime-specific identifiers like classification society report
numbers (DNV-RP-C203, ABS-CDS-2019-042, LR-2024/0012).

These identifiers are high-value fields — when found, they provide
definitive document identification with high confidence.
"""

from __future__ import annotations

import re

from docforge.models.fields import FieldValue


# =============================================================================
# General Identifier Patterns
# =============================================================================
# Each tuple: (regex_pattern, confidence, name)

REPORT_ID_PATTERNS: list[tuple[str, float, str]] = [
    # DOI (Digital Object Identifier) — most definitive
    (r'\bDOI[:\s]+(\S+)', 0.95, "doi"),
    (r'\b(10\.\d{4,}/\S+)', 0.95, "doi_raw"),

    # ISBN
    (r'\bISBN[:\s-]*([\dX-]{10,17})', 0.95, "isbn"),

    # arXiv
    (r'\barXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)', 0.95, "arxiv"),

    # IMO document numbers (e.g., MEPC.1/Circ.866, MSC.1/Circ.1503)
    (r'\b((?:MEPC|MSC|LEG|FAL|HTW|SSE|SDC|III|CCC)\.\d+/(?:Circ|WP|INF)\.\d+)', 0.90, "imo_doc"),

    # IMO resolution numbers (e.g., A.1104(30), MEPC.328(76))
    (r'\b((?:A|MEPC|MSC|LEG)\.\d+\(\d+\))', 0.90, "imo_resolution"),
]

# =============================================================================
# Maritime-Specific Identifier Patterns
# =============================================================================
# Classification society report numbers, drawing numbers, etc.

MARITIME_ID_PATTERNS: list[tuple[str, float, str]] = [
    # DNV patterns: DNV-RP-C203, DNV-ST-0119, DNV-OS-C101, DNV-GL-RP-0005
    (r'\b(DNV[-\s](?:RP|ST|OS|RU|SE|CG|CP)[-\s][A-Z]?\d{3,5})', 0.90, "dnv_doc"),

    # ABS patterns: ABS CDS-2019, ABS Guide for...
    (r'\b(ABS[-\s]\w+[-\s]\d{2,6})', 0.85, "abs_doc"),

    # Lloyd's Register: LR/2024/0012, ShipRight procedure
    (r'\b(LR[/\-]\d{4}[/\-]\d{3,6})', 0.85, "lr_doc"),

    # Bureau Veritas: NR/NI reference numbers
    (r'\b((?:NR|NI)\s*\d{3,5})', 0.85, "bv_doc"),

    # IACS URs and UIs: IACS UR S11, IACS UI SC123
    (r'\b(IACS\s+(?:UR|UI)\s+[A-Z]{1,3}\d{1,4})', 0.90, "iacs_doc"),

    # IMO number (vessel): 7-digit number
    (r'\bIMO\s*(?:No\.?|Number|#)?\s*(\d{7})\b', 0.90, "imo_number"),

    # Generic report/document number patterns
    (r'\b([A-Z]{2,10}[-/]\d{2,6}[-/]?\d{0,6})\b', 0.60, "generic_report_id"),

    # Drawing numbers: DWG-2023-045, DRG/2024/001
    (r'\b((?:DWG|DRG|DRAWING)[-/]\d{2,4}[-/]\d{2,6})', 0.80, "drawing_number"),

    # Project/document control numbers
    (r'\b(?:Doc(?:ument)?|Project|Ref(?:erence)?)\s*(?:No\.?|#|:)\s*'
     r'([A-Z0-9][-A-Z0-9/]{3,20})', 0.70, "doc_control_number"),

    # SOLAS/MARPOL chapter references
    (r'\b(SOLAS\s+(?:Ch(?:apter)?\.?\s*)?[IVXLC]+(?:\s*[-/]\s*\d+)?)', 0.85, "solas_ref"),
    (r'\b(MARPOL\s+Annex\s+[IVXLC]+)', 0.85, "marpol_ref"),
]


# =============================================================================
# Identifier Extraction
# =============================================================================

def extract_report_id(text: str, metadata: dict) -> FieldValue:
    """Extract the most likely document identifier from text and metadata.

    Searches for DOIs, ISBNs, classification society report numbers,
    IMO document references, drawing numbers, and generic report IDs.

    High-confidence identifiers (DOI, ISBN, arXiv) are preferred over
    generic report number patterns.

    Args:
        text:     Document text (first ~5000 chars recommended).
        metadata: PDF Info dictionary.

    Returns:
        FieldValue with the best identifier candidate.
    """
    candidates: list[FieldValue] = []

    # ── Strategy 1: PDF metadata subject/keywords ───────────────────────
    for key in ("subject", "Subject", "keywords", "Keywords"):
        if key in metadata and metadata[key]:
            value = str(metadata[key]).strip()
            # Check if it looks like an identifier
            if re.match(r'^[A-Z0-9][-A-Z0-9/.: ]{3,30}$', value):
                candidates.append(FieldValue(
                    value=value, confidence=0.55,
                    source="metadata",
                    extraction_method=f"pdf_{key}_as_id",
                ))

    # ── Strategy 2: High-confidence general identifiers ─────────────────
    search_text = text[:5000] if text else ""
    for pattern, conf, name in REPORT_ID_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            candidates.append(FieldValue(
                value=match.group(1).strip(),
                confidence=conf,
                source="heuristic",
                extraction_method=f"regex:{name}",
            ))

    # ── Strategy 3: Maritime-specific identifiers ───────────────────────
    for pattern, conf, name in MARITIME_ID_PATTERNS:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip() if match.lastindex else match.group(0).strip()
            candidates.append(FieldValue(
                value=value,
                confidence=conf,
                source="heuristic",
                extraction_method=f"regex:{name}",
            ))

    if candidates:
        return max(candidates, key=lambda c: c.confidence)

    return FieldValue(value=None, confidence=0.0, source="heuristic",
                      extraction_method="no_id_found")
