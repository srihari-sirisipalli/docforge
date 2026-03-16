"""Tests for Stage 2: Text extraction and quality scoring."""

import pytest

from docforge.extractors.text import TextExtractor, TextQualityScorer


class TestTextExtractor:
    """Test embedded text extraction from PDFs."""

    def test_extract_text(self, mock_pdf):
        extractor = TextExtractor(max_pages=2)
        text, quality = extractor.extract(mock_pdf)

        assert len(text) > 0
        assert quality > 0.0

    def test_extract_from_scanned_pdf(self, mock_pdf_scanned):
        extractor = TextExtractor(max_pages=2)
        text, quality = extractor.extract(mock_pdf_scanned)

        # Scanned PDF has no embedded text — quality should be low
        assert quality < 0.5

    def test_extract_nonexistent_file(self):
        extractor = TextExtractor()
        text, quality = extractor.extract("/nonexistent.pdf")
        assert text == ""
        assert quality == 0.0


class TestTextQualityScorer:
    """Test the text quality scoring algorithm."""

    def test_empty_text(self):
        assert TextQualityScorer.score("") == 0.0

    def test_short_text(self):
        assert TextQualityScorer.score("hi") == 0.0

    def test_good_english_text(self):
        text = (
            "This document provides the rules for classification of ships. "
            "The requirements cover hull structural design, machinery installation, "
            "safety equipment, fire protection, and survey procedures. "
            "All applicable international standards shall be followed."
        )
        score = TextQualityScorer.score(text)
        assert score > 0.5

    def test_garbage_text(self):
        text = "xjk2$# @!m nbv qz8 *&^ ll!! ppq"
        score = TextQualityScorer.score(text)
        assert score < 0.7  # Garbage text should score lower than good text

    def test_score_range(self):
        text = "The ship was built in accordance with the classification rules."
        score = TextQualityScorer.score(text)
        assert 0.0 <= score <= 1.0
