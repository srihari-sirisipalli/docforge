"""
DocForge — Test Configuration
================================

Shared pytest fixtures for the entire test suite.
Provides temporary databases, sample records, configs, and mock PDFs.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from docforge.infra.config import RuntimeConfig
from docforge.models.enums import DocumentStatus, ExtractionStrategy, MaritimeDocumentType
from docforge.models.fields import ExtractedFields, FieldValue, empty_fields
from docforge.models.record import DocumentRecord, PendingDocument
from docforge.storage.database import StateDB


# =============================================================================
# Temporary directory and database fixtures
# =============================================================================

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory that auto-cleans up."""
    return tmp_path


@pytest.fixture
def db_path(tmp_path):
    """Provide a path for a temporary SQLite database."""
    return str(tmp_path / "test_state.db")


@pytest.fixture
def db(db_path):
    """Create a fresh StateDB instance in a temp directory."""
    state_db = StateDB(db_path)
    yield state_db
    state_db.close()


# =============================================================================
# Configuration fixtures
# =============================================================================

@pytest.fixture
def config(tmp_path):
    """Provide a RuntimeConfig with paths pointing to temp directories."""
    cfg = RuntimeConfig()
    cfg.general.db_path = str(tmp_path / "state.db")
    cfg.general.log_path = str(tmp_path / "logs")
    cfg.general.temp_dir = str(tmp_path / "tmp")
    cfg.vlm.enabled = False  # Disable VLM in tests by default
    cfg.organizer.base_dir = str(tmp_path / "organized")
    cfg.safety.dry_run = True
    return cfg


# =============================================================================
# Sample data fixtures
# =============================================================================

@pytest.fixture
def sample_pending() -> list[PendingDocument]:
    """Create a list of sample PendingDocument records."""
    return [
        PendingDocument(
            file_id=f"hash_{i:04d}",
            original_path=f"/docs/sample_{i}.pdf",
            file_size_bytes=1024 * (i + 1),
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_fields() -> ExtractedFields:
    """Create sample ExtractedFields with realistic maritime data."""
    fields = empty_fields()
    fields.title = FieldValue(
        value="Rules for Classification of Ships",
        confidence=0.85,
        source="heuristic",
        extraction_method="largest_font_page1",
    )
    fields.author = FieldValue(
        value="Det Norske Veritas",
        confidence=0.80,
        source="heuristic",
        extraction_method="org_as_author",
    )
    fields.organization = FieldValue(
        value="DNV",
        confidence=0.90,
        source="heuristic",
        extraction_method="known_org_match",
    )
    fields.date = FieldValue(
        value="2023-07-15",
        confidence=0.85,
        source="metadata",
        extraction_method="pdf_creation_date",
    )
    fields.year = FieldValue(
        value="2023",
        confidence=0.85,
        source="metadata",
        extraction_method="year_from_date",
    )
    fields.report_id = FieldValue(
        value="DNV-RU-SHIP-Pt1Ch1",
        confidence=0.90,
        source="heuristic",
        extraction_method="regex:dnv_rules",
    )
    fields.maritime_document_type = FieldValue(
        value="class_rules",
        confidence=0.88,
        source="heuristic",
        extraction_method="maritime_signals",
    )
    fields.maritime_domain = FieldValue(
        value="classification_societies",
        confidence=0.88,
        source="heuristic",
        extraction_method="domain_from_type",
    )
    return fields


@pytest.fixture
def sample_record(sample_fields) -> DocumentRecord:
    """Create a complete DocumentRecord as it would look after Stage 5."""
    record = DocumentRecord(
        file_id="abc123def456",
        original_path="/docs/dnv_rules_ships_part1.pdf",
        file_size_bytes=2048576,
        page_count=150,
        raw_text="Rules for Classification of Ships Part 1 Chapter 1...",
        text_quality_score=0.85,
        extraction_strategy=ExtractionStrategy.TEXT_HEURISTIC.value,
        merged_fields=sample_fields,
        canonical_name="dnv_rules_classification_ships_dnv_ru_ship_pt1ch1_2023.pdf",
        target_directory="/organized/Classification_Societies/DNV/rules/",
        current_stage=5,
        status=DocumentStatus.COMPLETE,
        processing_time_ms=45,
    )
    return record


# =============================================================================
# Mock PDF fixture
# =============================================================================

@pytest.fixture
def mock_pdf(tmp_path) -> str:
    """Create a minimal valid PDF file for testing.

    Returns the path to the created PDF file.
    """
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4

        # Add some text
        page.insert_text(
            (72, 100),
            "Rules for Classification of Ships",
            fontsize=18,
        )
        page.insert_text(
            (72, 140),
            "Det Norske Veritas",
            fontsize=12,
        )
        page.insert_text(
            (72, 170),
            "DNV-RU-SHIP Pt.1 Ch.1",
            fontsize=10,
        )
        page.insert_text(
            (72, 200),
            "July 2023",
            fontsize=10,
        )
        page.insert_text(
            (72, 260),
            "This document contains the rules for classification "
            "and construction of steel ships. The requirements cover "
            "hull structural design, machinery, safety equipment, "
            "and survey procedures.",
            fontsize=10,
        )

        # Set metadata
        doc.set_metadata({
            "title": "Rules for Classification of Ships",
            "author": "DNV",
            "subject": "Classification Rules",
            "keywords": "DNV, classification, ships, rules, steel",
        })

        pdf_path = str(tmp_path / "test_document.pdf")
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    except ImportError:
        pytest.skip("PyMuPDF not available")


@pytest.fixture
def mock_pdf_scanned(tmp_path) -> str:
    """Create a minimal PDF with no embedded text (simulating a scan).

    Returns the path to the created PDF file.
    """
    try:
        import fitz
        from PIL import Image, ImageDraw, ImageFont

        # Create a simple image with text (as if scanned)
        img = Image.new("RGB", (595, 842), "white")
        draw = ImageDraw.Draw(img)
        draw.text((72, 100), "Scanned Document Title", fill="black")
        draw.text((72, 140), "Author Name Here", fill="black")

        img_path = str(tmp_path / "scan_page.png")
        img.save(img_path)

        # Create PDF from image (no embedded text)
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_image(fitz.Rect(0, 0, 595, 842), filename=img_path)

        pdf_path = str(tmp_path / "scanned_document.pdf")
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    except ImportError:
        pytest.skip("PyMuPDF or Pillow not available")


@pytest.fixture
def multiple_pdfs(tmp_path) -> list[str]:
    """Create several mock PDFs for scanner/pipeline testing."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not available")

    pdfs = []
    samples = [
        ("stability_report.pdf", "Intact Stability Analysis", "BV", "Bureau Veritas"),
        ("engine_manual.pdf", "Wartsila 12V46F Operation Manual", "Wartsila", "Wartsila"),
        ("survey_report.pdf", "Annual Survey Report MV Ocean Star", "LR", "Lloyd's Register"),
        ("mooring_analysis.pdf", "Mooring System Analysis FPSO", "ABS", "ABS"),
        ("imo_circular.pdf", "MSC.1/Circ.1228 Fire Safety", "IMO", "IMO"),
    ]

    for filename, title, org, author in samples:
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), title, fontsize=16)
        page.insert_text((72, 140), author, fontsize=12)
        page.insert_text(
            (72, 200),
            "This document provides detailed technical analysis and "
            "requirements for the subject matter described above. "
            "All specifications conform to applicable international standards.",
            fontsize=10,
        )
        doc.set_metadata({"title": title, "author": org})

        path = str(tmp_path / filename)
        doc.save(path)
        doc.close()
        pdfs.append(path)

    return pdfs
