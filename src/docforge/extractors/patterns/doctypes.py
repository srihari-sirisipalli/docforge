"""
DocForge — Document Type Classification
=========================================

Classifies documents into types using keyword/regex signal detection.
Contains both generic document type patterns and maritime domain-specific
patterns for classification societies, engineering, offshore, etc.

The classifier works by scoring each document type based on how many
signal patterns match in the text, then returning the highest scorer.
"""

from __future__ import annotations

import re
from typing import Optional

from docforge.models.enums import (
    DOCTYPE_TO_DOMAIN,
    KNOWN_MARITIME_ORGS,
    MaritimeDocumentType,
    MaritimeDomain,
)
from docforge.models.fields import FieldValue


# =============================================================================
# Generic Document Type Signals
# =============================================================================
# Each type maps to a list of (regex_pattern, weight) tuples.
# The type with the highest total weight wins.

DOCTYPE_SIGNALS: dict[str, list[tuple[str, int]]] = {
    "invoice": [
        (r'\b(?:invoice|bill|receipt|payment\s+due|amount\s+due)\b', 3),
        (r'\b(?:qty|quantity|unit\s+price|subtotal|tax)\b', 2),
        (r'\b(?:invoice\s*#|inv\s*no|bill\s*to)\b', 4),
    ],
    "research_paper": [
        (r'\b(?:abstract|introduction|methodology|conclusion|references)\b', 2),
        (r'\b(?:et\s+al\.|doi:|arxiv:)\b', 3),
    ],
    "manual": [
        (r'\b(?:user\s+manual|instruction|operation\s+guide|getting\s+started)\b', 4),
        (r'\b(?:chapter\s+\d+|section\s+\d+|step\s+\d+)\b', 2),
    ],
    "report": [
        (r'\b(?:technical\s+report|final\s+report|annual\s+report|quarterly)\b', 4),
        (r'\b(?:executive\s+summary|findings|recommendations)\b', 2),
    ],
    "letter": [
        (r'\b(?:dear\s+|sincerely|regards|to\s+whom\s+it\s+may\s+concern)\b', 4),
    ],
    "contract": [
        (r'\b(?:agreement|herein|whereas|party|parties|terms\s+and\s+conditions)\b', 3),
        (r'\b(?:shall|obligations|liability|indemnif)\b', 2),
    ],
    "presentation": [
        (r'\b(?:slide\s+\d+|presentation|agenda|overview)\b', 3),
    ],
}


# =============================================================================
# Maritime Document Type Signals
# =============================================================================
# Comprehensive patterns for engineering, maritime, and offshore domains.
# Each MaritimeDocumentType maps to signal patterns.

MARITIME_DOCTYPE_SIGNALS: dict[MaritimeDocumentType, list[tuple[str, int]]] = {

    # ── Classification Societies ─────────────────────────────────────────
    MaritimeDocumentType.CLASS_RULES: [
        (r'\b(?:rules?\s+for\s+classification|class(?:ification)?\s+rules?)\b', 5),
        (r'\b(?:rules?\s+for\s+(?:steel\s+)?ships?|rules?\s+for\s+offshore)\b', 5),
        (r'\b(?:part\s+\d+\s*[-:]\s*(?:hull|machinery|electrical|fire))\b', 3),
        (r'\b(?:rule\s+(?:change|amendment|corrigend))\b', 3),
        (r'\b(?:DNV[-\s](?:RU|OS)|ABS\s+Rules?|LR\s+Rules?|BV\s+(?:NR|Rules?))\b', 4),
    ],
    MaritimeDocumentType.CLASS_GUIDANCE: [
        (r'\b(?:guidance\s+note|recommended\s+practice|advisory)\b', 5),
        (r'\b(?:DNV[-\s]RP|DNV[-\s]CG|DNV[-\s]ST|ABS\s+Guide)\b', 5),
        (r'\b(?:class\s+guideline|technical\s+guidance)\b', 4),
    ],
    MaritimeDocumentType.CLASS_CERTIFICATE: [
        (r'\b(?:certificate\s+of\s+class|survey\s+certificate)\b', 5),
        (r'\b(?:type\s+approval|certificate\s+(?:no|number))\b', 4),
        (r'\b(?:annual\s+survey|intermediate\s+survey|special\s+survey)\b', 3),
        (r'\b(?:class\s+notation|notation\s+symbol)\b', 3),
    ],
    MaritimeDocumentType.CLASS_NOTATION: [
        (r'\b(?:class\s+notation|additional\s+notation|notation\s+symbol)\b', 5),
        (r'\b(?:ice\s+class|fi-fi|dp[-\s]?\d|clean\s+design)\b', 3),
    ],

    # ── Naval Architecture ───────────────────────────────────────────────
    MaritimeDocumentType.STABILITY_ANALYSIS: [
        (r'\b(?:stability|metacentric\s+height|gz\s+curve|righting\s+lever)\b', 4),
        (r'\b(?:intact\s+stability|damage\s+stability|stability\s+booklet)\b', 5),
        (r'\b(?:loading\s+condition|displacement|deadweight|trim)\b', 3),
        (r'\b(?:imo\s+(?:criteria|code)\s+.*stability|is\s+code)\b', 4),
        (r'\b(?:grain\s+stability|probabilistic\s+damage)\b', 4),
    ],
    MaritimeDocumentType.STRUCTURAL_ANALYSIS: [
        (r'\b(?:structural\s+(?:analysis|calculation|design|assessment))\b', 5),
        (r'\b(?:midship\s+section|scantling|hull\s+girder|section\s+modulus)\b', 5),
        (r'\b(?:fatigue\s+(?:analysis|life|assessment|damage))\b', 4),
        (r'\b(?:buckling|yield|ultimate\s+strength|bending\s+moment)\b', 3),
        (r'\b(?:plate\s+thickness|stiffener|frame\s+spacing|web\s+frame)\b', 3),
    ],
    MaritimeDocumentType.HYDRODYNAMIC_ANALYSIS: [
        (r'\b(?:resistance\s+(?:and\s+)?propulsion|speed[-\s]power)\b', 5),
        (r'\b(?:seakeeping|ship\s+motion|wave[-\s]induced|rao)\b', 4),
        (r'\b(?:manoeuvring|turning\s+circle|zig[-\s]zag|stopping\s+distance)\b', 4),
        (r'\b(?:wake\s+fraction|thrust\s+deduction|propeller\s+efficiency)\b', 3),
        (r'\b(?:cfd|computational\s+fluid|navier[-\s]stokes|rans)\b', 3),
    ],
    MaritimeDocumentType.LINES_PLAN: [
        (r'\b(?:lines?\s+plan|body\s+plan|waterline|buttock)\b', 5),
        (r'\b(?:hull\s+form|offset\s+table|table\s+of\s+offsets)\b', 4),
    ],
    MaritimeDocumentType.GENERAL_ARRANGEMENT: [
        (r'\b(?:general\s+arrangement|g\.?a\.?\s+plan|deck\s+plan)\b', 5),
        (r'\b(?:profile\s+view|plan\s+view|arrangement\s+drawing)\b', 4),
        (r'\b(?:accommodation|engine\s+room\s+(?:layout|arrangement))\b', 3),
    ],

    # ── Marine Operations ────────────────────────────────────────────────
    MaritimeDocumentType.VOYAGE_PLAN: [
        (r'\b(?:voyage\s+plan|passage\s+plan|sailing\s+directions)\b', 5),
        (r'\b(?:waypoint|eta|etd|port\s+of\s+call)\b', 3),
    ],
    MaritimeDocumentType.CARGO_PLAN: [
        (r'\b(?:cargo\s+(?:plan|stowage|manifest|securing))\b', 5),
        (r'\b(?:loading\s+(?:sequence|plan)|discharge\s+plan)\b', 4),
        (r'\b(?:container\s+(?:plan|bay)|hold\s+capacity)\b', 3),
    ],
    MaritimeDocumentType.BALLAST_PLAN: [
        (r'\b(?:ballast\s+(?:water|management|plan|exchange))\b', 5),
        (r'\b(?:bwms|ballast\s+treatment|d-?\d\s+standard)\b', 4),
    ],
    MaritimeDocumentType.SURVEY_REPORT: [
        (r'\b(?:survey\s+report|condition\s+(?:survey|assessment))\b', 5),
        (r'\b(?:hull\s+(?:survey|condition)|thickness\s+measurement)\b', 4),
        (r'\b(?:class\s+(?:renewal|survey)|annual\s+survey|dry[-\s]?dock)\b', 4),
        (r'\b(?:underwater\s+(?:survey|inspection))\b', 4),
    ],
    MaritimeDocumentType.INSPECTION_REPORT: [
        (r'\b(?:inspection\s+report|port\s+state\s+(?:control|inspection))\b', 5),
        (r'\b(?:psc\s+(?:report|inspection)|vetting\s+(?:report|inspection))\b', 5),
        (r'\b(?:sire\s+inspection|cdi\s+inspection|rightship)\b', 4),
        (r'\b(?:deficiency|observation|non[-\s]?conform)', 3),
    ],
    MaritimeDocumentType.INCIDENT_REPORT: [
        (r'\b(?:incident\s+(?:report|investigation)|accident\s+(?:report|analysis))\b', 5),
        (r'\b(?:near[-\s]?miss|root\s+cause|corrective\s+action)\b', 4),
        (r'\b(?:casualty\s+(?:report|investigation)|safety\s+alert)\b', 4),
    ],
    MaritimeDocumentType.PROCEDURE_SOP: [
        (r'\b(?:procedure|standard\s+operating|work\s+instruction)\b', 4),
        (r'\b(?:checklist|step[-\s]by[-\s]step|sop)\b', 3),
        (r'\b(?:emergency\s+(?:procedure|drill)|muster\s+list)\b', 4),
        (r'\b(?:safe\s+(?:working|operating)\s+practice)\b', 3),
    ],

    # ── Offshore & Subsea ────────────────────────────────────────────────
    MaritimeDocumentType.PIPELINE_DESIGN: [
        (r'\b(?:pipeline\s+(?:design|engineering|routing|installation))\b', 5),
        (r'\b(?:subsea\s+pipeline|flowline|umbilical|riser[-\s]?base)\b', 4),
        (r'\b(?:on[-\s]?bottom\s+stability|free[-\s]?span|cathodic\s+protection)\b', 3),
    ],
    MaritimeDocumentType.RISER_ANALYSIS: [
        (r'\b(?:riser\s+(?:analysis|design|configuration|system))\b', 5),
        (r'\b(?:vortex[-\s]?induced|viv|sct\s+riser|flexible\s+riser)\b', 4),
        (r'\b(?:top[-\s]?tension|ttf|fatigue\s+life\s+.*riser)\b', 4),
    ],
    MaritimeDocumentType.MOORING_ANALYSIS: [
        (r'\b(?:mooring\s+(?:analysis|design|system|line))\b', 5),
        (r'\b(?:anchor\s+(?:holding|capacity|design)|chain\s+(?:size|design))\b', 4),
        (r'\b(?:turret\s+mooring|spread\s+mooring|single\s+point)\b', 4),
        (r'\b(?:line\s+tension|offset\s+analysis|mooring\s+pattern)\b', 3),
    ],
    MaritimeDocumentType.FEA_REPORT: [
        (r'\b(?:finite\s+element|fea\s+(?:report|analysis|results?))\b', 5),
        (r'\b(?:stress\s+(?:analysis|distribution|concentration))\b', 3),
        (r'\b(?:mesh\s+(?:size|density|convergence)|boundary\s+condition)\b', 3),
        (r'\b(?:von\s+mises|principal\s+stress|ansys|abaqus|nastran)\b', 4),
    ],
    MaritimeDocumentType.CFD_REPORT: [
        (r'\b(?:cfd\s+(?:report|analysis|simulation|results?))\b', 5),
        (r'\b(?:computational\s+fluid\s+dynamics|flow\s+simulation)\b', 5),
        (r'\b(?:turbulence\s+model|k[-\s]epsilon|sst|les)\b', 3),
    ],
    MaritimeDocumentType.INSTALLATION_REPORT: [
        (r'\b(?:installation\s+(?:report|procedure|analysis|plan))\b', 5),
        (r'\b(?:heavy[-\s]?lift|loadout|float[-\s]?over|jacket\s+launch)\b', 4),
        (r'\b(?:rigging\s+(?:plan|analysis)|crane\s+(?:capacity|analysis))\b', 3),
    ],
    MaritimeDocumentType.FEED_STUDY: [
        (r'\b(?:feed\s+(?:study|report)|front[-\s]?end\s+engineering)\b', 5),
        (r'\b(?:concept\s+(?:selection|study|design)|pre[-\s]?feed)\b', 4),
        (r'\b(?:feasibility\s+study|basis\s+of\s+design)\b', 4),
    ],

    # ── Equipment Manuals ────────────────────────────────────────────────
    MaritimeDocumentType.ENGINE_MANUAL: [
        (r'\b(?:(?:main\s+)?engine\s+(?:manual|handbook|instruction))\b', 5),
        (r'\b(?:wartsila|man\s+b&w|caterpillar|mak|bergen)\b', 3),
        (r'\b(?:cylinder\s+(?:head|liner)|turbocharger|fuel\s+injection)\b', 3),
        (r'\b(?:crankshaft|camshaft|exhaust\s+valve|scavenge)\b', 3),
    ],
    MaritimeDocumentType.EQUIPMENT_MANUAL: [
        (r'\b(?:(?:operation|maintenance|service)\s+(?:manual|handbook|guide))\b', 4),
        (r'\b(?:pump|compressor|separator|purifier|heat\s+exchanger)\b', 3),
        (r'\b(?:spare\s+parts?|troubleshoot|overhaul|maintenance\s+schedule)\b', 3),
    ],
    MaritimeDocumentType.NAVIGATION_MANUAL: [
        (r'\b(?:(?:radar|ecdis|ais|gps|gyro(?:compass)?)\s+(?:manual|handbook))\b', 5),
        (r'\b(?:navigation\s+(?:equipment|system)\s+(?:manual|guide))\b', 5),
        (r'\b(?:furuno|jrc|sperry|transas|kongsberg)\b', 3),
    ],
    MaritimeDocumentType.ELECTRICAL_MANUAL: [
        (r'\b(?:electrical\s+(?:manual|system|diagram|drawing))\b', 5),
        (r'\b(?:switchboard|generator|transformer|motor\s+control)\b', 3),
        (r'\b(?:single[-\s]line\s+diagram|power\s+management)\b', 3),
    ],

    # ── Regulatory ───────────────────────────────────────────────────────
    MaritimeDocumentType.IMO_DOCUMENT: [
        (r'\b(?:imo\s+(?:convention|resolution|circular|guideline))\b', 5),
        (r'\b(?:solas|marpol|stcw|llc|tonnage\s+convention)\b', 4),
        (r'\b(?:mepc|msc|assembly\s+resolution|imo\s+instruments?)\b', 4),
    ],
    MaritimeDocumentType.FLAG_STATE_DOCUMENT: [
        (r'\b(?:flag\s+state|marine\s+(?:notice|guidance\s+note))\b', 5),
        (r'\b(?:mgn|min\s+\d|shipping\s+notice|flag\s+circular)\b', 4),
        (r'\b(?:statutory\s+(?:instrument|requirement)|flag\s+admin)\b', 3),
    ],
    MaritimeDocumentType.PORT_STATE_DOCUMENT: [
        (r'\b(?:port\s+state\s+control|psc\s+(?:guideline|regime))\b', 5),
        (r'\b(?:paris\s+mou|tokyo\s+mou|indian\s+ocean\s+mou)\b', 4),
        (r'\b(?:detention|nil[-\s]deficiency|target\s+factor)\b', 3),
    ],
    MaritimeDocumentType.ISM_ISPS: [
        (r'\b(?:ism\s+code|isps\s+code|safety\s+management\s+system)\b', 5),
        (r'\b(?:sms\s+(?:manual|procedure)|doc\s+of\s+compliance)\b', 4),
        (r'\b(?:ship\s+security\s+(?:plan|assessment)|pfso|sso|cso)\b', 4),
    ],

    # ── Research ─────────────────────────────────────────────────────────
    MaritimeDocumentType.RESEARCH_PAPER: [
        (r'\b(?:abstract|introduction|methodology|conclusion|references)\b', 2),
        (r'\b(?:et\s+al\.|doi:|arxiv:|journal\s+of)\b', 3),
        (r'\b(?:ocean\s+engineering|marine\s+(?:structures?|technology))\b', 3),
        (r'\b(?:omae|isope|rina\s+transactions?|sname)\b', 4),
    ],
    MaritimeDocumentType.THESIS: [
        (r'\b(?:thesis|dissertation|submitted\s+(?:to|for)\s+.*degree)\b', 5),
        (r'\b(?:master(?:\s+of)?|(?:ph\.?)?d\.?\s+(?:thesis|dissertation))\b', 5),
        (r'\b(?:supervisor|examiner|department\s+of)\b', 2),
    ],
    MaritimeDocumentType.CONFERENCE_PAPER: [
        (r'\b(?:conference\s+(?:paper|proceedings?)|presented\s+at)\b', 5),
        (r'\b(?:omae[-\s]?\d{4}|isope[-\s]?\d{4}|rina\s+conference)\b', 5),
        (r'\b(?:compit|imam|hsmv|fast\s+conference)\b', 4),
    ],

    # ── Commercial ───────────────────────────────────────────────────────
    MaritimeDocumentType.CONTRACT: [
        (r'\b(?:(?:ship[-\s]?building|repair|charter)\s+contract)\b', 5),
        (r'\b(?:charter\s+party|time[-\s]?charter|voyage[-\s]?charter)\b', 5),
        (r'\b(?:newbuild(?:ing)?\s+contract|hull\s+(?:no|number))\b', 4),
        (r'\b(?:dry[-\s]?dock(?:ing)?\s+(?:contract|agreement))\b', 4),
    ],
    MaritimeDocumentType.INVOICE: [
        (r'\b(?:invoice|proforma|debit\s+note|credit\s+note)\b', 4),
        (r'\b(?:invoice\s*(?:#|no|number)|payment\s+terms?)\b', 4),
    ],
    MaritimeDocumentType.PROPOSAL: [
        (r'\b(?:proposal|quotation|tender|bid)\b', 3),
        (r'\b(?:scope\s+of\s+(?:work|supply)|price\s+(?:list|schedule))\b', 3),
    ],
    MaritimeDocumentType.CORRESPONDENCE: [
        (r'\b(?:dear\s+|sincerely|regards|attention\s+of)\b', 3),
        (r'\b(?:letter\s+of\s+(?:intent|protest|indemnity))\b', 4),
    ],
    MaritimeDocumentType.MEETING_MINUTES: [
        (r'\b(?:(?:meeting\s+)?minutes?|mom\b|minute\s+of\s+meeting)\b', 5),
        (r'\b(?:action\s+(?:items?|points?)|attendees?|agenda)\b', 3),
        (r'\b(?:progress\s+(?:meeting|review)|kick[-\s]?off)\b', 3),
    ],

    # ── General ──────────────────────────────────────────────────────────
    MaritimeDocumentType.TECHNICAL_REPORT: [
        (r'\b(?:technical\s+report|engineering\s+report)\b', 4),
        (r'\b(?:executive\s+summary|findings|recommendations)\b', 2),
    ],
    MaritimeDocumentType.DATASHEET: [
        (r'\b(?:data[-\s]?sheet|specification\s+sheet|product\s+data)\b', 5),
        (r'\b(?:technical\s+(?:data|specification)|model\s+(?:no|number))\b', 3),
    ],
    MaritimeDocumentType.SPECIFICATION: [
        (r'\b(?:technical\s+specification|material\s+specification)\b', 5),
        (r'\b(?:spec(?:ification)?\s+(?:no|number|ref))\b', 3),
        (r'\b(?:coating\s+spec|paint\s+spec|steel\s+spec)\b', 4),
    ],
    MaritimeDocumentType.DRAWING: [
        (r'\b(?:(?:technical\s+)?drawing|schematic|diagram)\b', 3),
        (r'\b(?:p&id|piping\s+(?:and\s+)?instrument|wiring\s+diagram)\b', 4),
        (r'\b(?:isometric|orthographic|detail\s+drawing)\b', 3),
    ],
    MaritimeDocumentType.PRESENTATION: [
        (r'\b(?:presentation|slide\s+deck|overview)\b', 3),
        (r'\b(?:agenda|q&a|discussion\s+points?)\b', 2),
    ],
}


# =============================================================================
# Organisation Detection
# =============================================================================

# Compiled regex patterns for known maritime organisations
_ORG_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(rf'\b{re.escape(name)}\b', re.IGNORECASE), abbrev)
    for name, abbrev in KNOWN_MARITIME_ORGS.items()
    if len(name) > 3  # Skip very short abbreviations for regex safety
]


def detect_organisation(text: str, metadata: dict) -> FieldValue:
    """Detect the publishing organisation from text and metadata.

    Checks against a comprehensive list of known maritime organisations
    (classification societies, shipyards, engine makers, operators).

    Args:
        text:     Document text.
        metadata: PDF Info dictionary.

    Returns:
        FieldValue with the detected organisation abbreviation.
    """
    candidates: list[FieldValue] = []

    # Check metadata first
    search_sources = []
    for key in ("author", "Author", "creator", "Creator", "producer", "Producer"):
        if key in metadata and metadata[key]:
            search_sources.append((str(metadata[key]), 0.70, "metadata"))

    # Check text
    if text:
        search_sources.append((text[:3000], 0.75, "heuristic"))

    for source_text, base_conf, source_name in search_sources:
        lower_text = source_text.lower()
        for full_name, abbrev in KNOWN_MARITIME_ORGS.items():
            # Short names (<=3 chars) need word-boundary matching to avoid
            # false positives (e.g., "rs" matching "yours", "first", etc.)
            if len(full_name) <= 3:
                if re.search(rf'\b{re.escape(full_name)}\b', lower_text):
                    candidates.append(FieldValue(
                        value=abbrev,
                        confidence=base_conf * 0.8,  # Lower confidence for short matches
                        source=source_name,
                        extraction_method=f"org_match:{full_name}",
                    ))
            elif full_name in lower_text:
                candidates.append(FieldValue(
                    value=abbrev,
                    confidence=base_conf,
                    source=source_name,
                    extraction_method=f"org_match:{full_name}",
                ))

    if candidates:
        return max(candidates, key=lambda c: c.confidence)

    return FieldValue(value=None, confidence=0.0, source="heuristic",
                      extraction_method="no_org_found")


# =============================================================================
# Document Type Classification
# =============================================================================

def classify_document_type(text: str) -> FieldValue:
    """Classify document into a generic type using keyword signals.

    Args:
        text: Document text.

    Returns:
        FieldValue with the detected document type.
    """
    if not text:
        return FieldValue(value="other", confidence=0.1, source="heuristic",
                          extraction_method="no_text")

    lower = text[:10000].lower()
    scores: dict[str, float] = {}

    for doc_type, patterns in DOCTYPE_SIGNALS.items():
        score = 0.0
        for pattern, weight in patterns:
            if re.search(pattern, lower, re.IGNORECASE):
                score += weight
        if score > 0:
            scores[doc_type] = score

    if scores:
        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        max_possible = sum(w for _, w in DOCTYPE_SIGNALS[best_type])
        confidence = min(scores[best_type] / max(max_possible, 1) * 0.85, 0.90)
        return FieldValue(
            value=best_type, confidence=confidence,
            source="heuristic", extraction_method="doctype_signals",
        )

    return FieldValue(value="other", confidence=0.1, source="heuristic",
                      extraction_method="doctype_no_match")


def classify_maritime_document(
    text: str, metadata: dict
) -> tuple[FieldValue, FieldValue, FieldValue]:
    """Classify a document into a maritime-specific type, domain, and subdomain.

    Scans text against all MARITIME_DOCTYPE_SIGNALS patterns, scores each
    type, and returns the best match along with its parent domain.

    Args:
        text:     Document text (first ~10000 chars).
        metadata: PDF Info dictionary.

    Returns:
        Tuple of (maritime_type, maritime_domain, maritime_subdomain) FieldValues.
    """
    if not text:
        return (
            FieldValue(value=MaritimeDocumentType.OTHER.value, confidence=0.1,
                       source="heuristic", extraction_method="no_text"),
            FieldValue(value=MaritimeDomain.GENERAL.value, confidence=0.1,
                       source="heuristic", extraction_method="no_text"),
            FieldValue(value="", confidence=0.0,
                       source="heuristic", extraction_method="no_text"),
        )

    lower = text[:10000].lower()
    scores: dict[MaritimeDocumentType, float] = {}

    # Score each maritime document type
    for doc_type, patterns in MARITIME_DOCTYPE_SIGNALS.items():
        score = 0.0
        for pattern, weight in patterns:
            if re.search(pattern, lower, re.IGNORECASE):
                score += weight
        if score > 0:
            scores[doc_type] = score

    if scores:
        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        max_possible = sum(w for _, w in MARITIME_DOCTYPE_SIGNALS[best_type])
        confidence = min(scores[best_type] / max(max_possible, 1) * 0.85, 0.90)

        # Look up domain
        domain = DOCTYPE_TO_DOMAIN.get(best_type, MaritimeDomain.GENERAL)

        # Determine subdomain from organisation
        org = detect_organisation(text, metadata)
        subdomain = org.value if org.value else best_type.value.split("_")[0]

        return (
            FieldValue(value=best_type.value, confidence=confidence,
                       source="heuristic", extraction_method="maritime_signals"),
            FieldValue(value=domain.value, confidence=confidence,
                       source="heuristic", extraction_method="maritime_domain"),
            FieldValue(value=subdomain, confidence=org.confidence if org.value else 0.3,
                       source="heuristic", extraction_method="maritime_subdomain"),
        )

    # Fallback to generic classification
    generic = classify_document_type(text)
    return (
        FieldValue(value=MaritimeDocumentType.OTHER.value, confidence=0.15,
                   source="heuristic", extraction_method="maritime_fallback"),
        FieldValue(value=MaritimeDomain.GENERAL.value, confidence=0.15,
                   source="heuristic", extraction_method="maritime_fallback"),
        FieldValue(value="", confidence=0.0,
                   source="heuristic", extraction_method="maritime_fallback"),
    )
