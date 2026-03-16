"""Tests for Stage 3 Path B: Heuristic extraction."""

import pytest

from docforge.extractors.heuristic import HeuristicExtractor
from docforge.models.record import DocumentRecord


class TestHeuristicExtractor:
    """Test rule-based field extraction."""

    def test_extract_from_mock_pdf(self, mock_pdf):
        record = DocumentRecord(
            file_id="test123",
            original_path=mock_pdf,
        )
        # Simulate Stage 2 output
        record.raw_text = (
            "Rules for Classification of Ships\n"
            "Det Norske Veritas\n"
            "DNV-RU-SHIP Pt.1 Ch.1\n"
            "July 2023\n"
            "This document contains the rules for classification.\n"
        )
        record.pdf_metadata = {"title": "Rules for Classification of Ships", "author": "DNV"}

        extractor = HeuristicExtractor()
        extractor.process(record)

        assert record.heuristic_fields is not None
        assert not record.heuristic_fields.organization.is_empty()
        assert record.heuristic_fields.organization.value == "DNV"

    def test_extract_date(self, mock_pdf):
        record = DocumentRecord(file_id="t", original_path=mock_pdf)
        record.raw_text = "Report dated 2023-07-15. Prepared by ABS."
        record.pdf_metadata = {}

        extractor = HeuristicExtractor()
        extractor.process(record)

        assert not record.heuristic_fields.date.is_empty()
        assert "2023" in record.heuristic_fields.date.value

    def test_extract_empty_text(self, mock_pdf):
        record = DocumentRecord(file_id="t", original_path=mock_pdf)
        record.raw_text = ""
        record.pdf_metadata = {}

        extractor = HeuristicExtractor()
        extractor.process(record)

        # Should not crash — fields may be empty but should exist
        assert record.heuristic_fields is not None
