"""Tests for Stage 1: Metadata extraction and file ID computation."""

import pytest

from docforge.extractors.metadata import MetadataExtractor, compute_file_id
from docforge.models.record import DocumentRecord


class TestComputeFileId:
    """Test the file_id computation (SHA-256 of first 64KB + size)."""

    def test_compute_file_id(self, mock_pdf):
        file_id = compute_file_id(mock_pdf)
        assert isinstance(file_id, str)
        assert len(file_id) == 64  # SHA-256 hex

    def test_same_file_same_id(self, mock_pdf):
        id1 = compute_file_id(mock_pdf)
        id2 = compute_file_id(mock_pdf)
        assert id1 == id2

    def test_nonexistent_file_raises(self):
        with pytest.raises(OSError):
            compute_file_id("/nonexistent/file.pdf")


class TestMetadataExtractor:
    """Test PDF metadata extraction."""

    def test_extract_metadata(self, mock_pdf):
        record = DocumentRecord(
            file_id="test123",
            original_path=mock_pdf,
        )
        extractor = MetadataExtractor()
        extractor.process(record)

        assert record.page_count >= 1
        assert record.pdf_metadata is not None
        assert record.current_stage == 1

    def test_extract_title(self, mock_pdf):
        record = DocumentRecord(file_id="test", original_path=mock_pdf)
        extractor = MetadataExtractor()
        extractor.process(record)

        # Mock PDF has metadata title set
        title = record.metadata_fields.title
        assert not title.is_empty()
        assert "Rules" in title.value or "Classification" in title.value

    def test_extract_from_invalid_path(self):
        record = DocumentRecord(file_id="bad", original_path="/nonexistent.pdf")
        extractor = MetadataExtractor()
        extractor.process(record)
        assert record.error_message != ""
