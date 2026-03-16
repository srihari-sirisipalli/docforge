"""
DocForge — VLM Prompt Templates
==================================

Prompts for Vision-Language Model extraction.
The primary prompt asks the VLM to directly generate a descriptive filename.
"""

from __future__ import annotations


# =============================================================================
# Filename Generation Prompt
# =============================================================================

VLM_FILENAME_PROMPT = """Look at this document image. Generate a descriptive filename.

FORMAT: word1_word2_word3_word4_year
- MUST use underscores _ between EVERY word
- All lowercase
- Max 8 words
- No file extension
- Do NOT include acronyms if the full form is already in the name
- Skip redundant words like "new", "copy", "english", "final", "draft"
- Return ONLY the filename on one line, nothing else

EXAMPLES:
srihari_deep_learning_coursera_certificate_2020
corteva_internship_offer_letter_2022
pangeon_invoice_march_2024
aadhar_card_srihari_2023
ssc_marks_list_2018
driving_license_srihari_2021
btech_degree_certificate_2022
euler_maruyama_sde_option_pricing_report_2022
quantum_superposition_neutrino_project_report

FILENAME:"""


# =============================================================================
# Metadata Extraction Prompt (for detailed extraction when needed)
# =============================================================================

VLM_EXTRACTION_PROMPT = """You are a document metadata extraction system. Analyse this document page image and extract metadata.

EXTRACT THESE FIELDS:
- title: The main document title (be concise, max 8 words)
- author: Primary author or person name
- organization: The issuing company, institution, or government body
- date: Date in YYYY-MM-DD format (use YYYY-MM or YYYY if partial)
- report_id: Any document number, certificate number, ID number, invoice number
- document_type: One of: certificate, academic_transcript, id_card, license, invoice, receipt, offer_letter, appointment_letter, contract, agreement, project_report, research_paper, thesis, resume, presentation, manual, form, correspondence, other
- keywords: Up to 5 key topic words, comma-separated
- summary: One sentence describing the document

RULES:
- Return ONLY valid JSON, no explanation or markdown
- Use null for fields you cannot confidently determine
- Be conservative: null is better than a guess
- Keep title concise and descriptive
- Read ALL visible text including headers, footers, logos, stamps

JSON:"""


# =============================================================================
# Diagram/Drawing Prompt
# =============================================================================

VLM_DIAGRAM_PROMPT = """You are analysing a document image. Extract metadata.

Extract:
- title: The document title or heading (concise, max 8 words)
- organization: Issuing company or institution
- report_id: Any document or reference number
- document_type: One of: certificate, id_card, form, drawing, diagram, other
- keywords: Key topics depicted
- summary: One sentence describing what this shows

Return ONLY valid JSON, no explanation. Use null for unknown fields.

JSON:"""


# =============================================================================
# Prompt Builder
# =============================================================================

def build_vlm_prompt(record, diagram_mode: bool = False) -> str:
    """Build the VLM prompt for filename generation.

    Args:
        record:       DocumentRecord with metadata_fields potentially populated.
        diagram_mode: If True, use the specialised diagram prompt.

    Returns:
        Complete prompt string for the VLM.
    """
    if diagram_mode:
        return VLM_DIAGRAM_PROMPT

    prompt = VLM_FILENAME_PROMPT

    # Add context from the original filename
    if record.original_path:
        import os
        original_name = os.path.basename(record.original_path)
        prompt += f"\n\nOriginal filename was: {original_name}"

    prompt += "\n\nFILENAME:"

    return prompt


def build_extraction_prompt(record) -> str:
    """Build the VLM prompt for detailed metadata extraction.

    Args:
        record: DocumentRecord with metadata_fields potentially populated.

    Returns:
        Complete prompt string for the VLM.
    """
    prompt = VLM_EXTRACTION_PROMPT

    # Add known metadata as context hints
    context_lines: list[str] = []
    if record.metadata_fields:
        mf = record.metadata_fields
        if not mf.title.is_empty():
            context_lines.append(f"PDF metadata title: {mf.title.value}")
        if not mf.author.is_empty():
            context_lines.append(f"PDF metadata author: {mf.author.value}")
        if not mf.date.is_empty():
            context_lines.append(f"PDF metadata date: {mf.date.value}")

    if context_lines:
        prompt += "\n\nALREADY KNOWN FROM PDF METADATA (verify or override based on what you see):\n"
        prompt += "\n".join(f"  - {line}" for line in context_lines)
        prompt += "\n\nJSON:"

    return prompt
