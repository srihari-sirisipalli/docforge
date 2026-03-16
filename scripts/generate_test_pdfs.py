#!/usr/bin/env python3
"""
Generate Test PDF Collection
================================

Creates a synthetic collection of PDF documents for testing DocForge.
Generates diverse document types with realistic metadata, text content,
and varying qualities (clean text, mixed, image-only).

Usage:
    python scripts/generate_test_pdfs.py [--output ./test_pdfs] [--count 50]
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

try:
    import fitz
except ImportError:
    print("PyMuPDF required: pip install PyMuPDF")
    raise SystemExit(1)


# Sample data for generating realistic documents
ORGS = ["DNV", "Lloyd's Register", "ABS", "Bureau Veritas", "RINA", "ClassNK",
        "IMO", "Wartsila", "MAN Energy", "Rolls-Royce", "Subsea 7", "TechnipFMC"]

DOC_TYPES = [
    ("Rules for Classification of {topic}", "class_rules"),
    ("Survey Report — {topic}", "survey_report"),
    ("{topic} Operation Manual", "equipment_manual"),
    ("Stability Analysis: {topic}", "stability_analysis"),
    ("Structural Analysis Report: {topic}", "structural_analysis"),
    ("Mooring System Design: {topic}", "mooring_analysis"),
    ("{topic} Installation Procedure", "installation_report"),
    ("MSC Circular: {topic}", "imo_document"),
    ("Research Paper: {topic}", "research_paper"),
    ("Technical Specification: {topic}", "specification"),
    ("CFD Analysis: {topic}", "cfd_report"),
    ("FEA Report: {topic}", "fea_report"),
    ("Invoice for {topic}", "invoice"),
    ("Meeting Minutes: {topic}", "meeting_minutes"),
    ("General Arrangement: {topic}", "general_arrangement"),
]

TOPICS = [
    "Steel Ships Part 1", "Bulk Carriers", "Oil Tankers",
    "FPSO Hull Structure", "Jack-up Platform", "Semi-submersible",
    "MV Ocean Star", "MT Pacific Voyager", "Container Ship Hull Design",
    "Wartsila 12V46F Engine", "MAN B&W 6S60MC-C", "Ballast Water Treatment",
    "Fire Safety Systems", "Navigation Equipment", "Propeller Design",
    "Offshore Wind Turbine Foundation", "Subsea Pipeline", "Riser System",
    "Dynamic Positioning System", "Crane Operations", "Helicopter Deck",
    "SOLAS Chapter II", "MARPOL Annex VI", "International Load Line Convention",
]

BODY_TEXT = (
    "This document provides comprehensive technical analysis and specifications "
    "for the subject matter. All requirements conform to applicable international "
    "standards and classification society rules.\n\n"
    "Section 1: General Requirements\n"
    "The design shall comply with the applicable rules and regulations. "
    "Materials shall be tested in accordance with the approved procedures. "
    "All calculations shall be verified by an independent reviewer.\n\n"
    "Section 2: Design Criteria\n"
    "The structure shall be designed to withstand the specified loads with "
    "adequate safety margins. Environmental conditions shall be determined "
    "based on site-specific data and established standards.\n\n"
    "Section 3: Analysis Results\n"
    "The analysis demonstrates that all acceptance criteria are satisfied. "
    "Maximum stress levels are within allowable limits. Fatigue life exceeds "
    "the required design life with a safety factor of 3.0.\n"
)


def generate_pdf(output_dir: Path, index: int) -> str:
    """Generate a single test PDF with random metadata."""
    template, doc_type = random.choice(DOC_TYPES)
    topic = random.choice(TOPICS)
    org = random.choice(ORGS)
    year = random.randint(2015, 2024)
    title = template.format(topic=topic)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Title
    page.insert_text((72, 80), title, fontsize=16)
    page.insert_text((72, 110), org, fontsize=12)
    page.insert_text((72, 135), f"Report No. {org[:3]}-{year}-{index:04d}", fontsize=10)
    page.insert_text((72, 155), f"Date: {year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}", fontsize=10)

    # Body text
    y = 200
    for line in BODY_TEXT.split("\n"):
        if line.strip():
            page.insert_text((72, y), line[:90], fontsize=10)
            y += 15
            if len(line) > 90:
                page.insert_text((72, y), line[90:], fontsize=10)
                y += 15
        else:
            y += 10
        if y > 780:
            break

    # Add a second page for some documents
    if random.random() > 0.3:
        page2 = doc.new_page(width=595, height=842)
        page2.insert_text((72, 80), f"{title} (continued)", fontsize=12)
        page2.insert_text(
            (72, 120),
            "Additional technical details and appendices follow.",
            fontsize=10,
        )

    # Set metadata
    doc.set_metadata({
        "title": title,
        "author": org,
        "subject": doc_type.replace("_", " ").title(),
        "keywords": f"{org}, {topic}, {doc_type}",
    })

    # Generate filename
    safe_title = title[:40].replace(" ", "_").replace(":", "").replace("/", "_")
    filename = f"{safe_title}_{year}.pdf"
    output_path = output_dir / filename
    doc.save(str(output_path))
    doc.close()

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Generate test PDF collection")
    parser.add_argument("--output", "-o", default="./test_pdfs",
                        help="Output directory (default: ./test_pdfs)")
    parser.add_argument("--count", "-n", type=int, default=50,
                        help="Number of PDFs to generate (default: 50)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} test PDFs in {output_dir}...")

    for i in range(args.count):
        path = generate_pdf(output_dir, i)
        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{args.count} generated")

    print(f"\nDone! {args.count} PDFs created in {output_dir}")
    print(f"\nTest with: docforge process {output_dir}")


if __name__ == "__main__":
    main()
