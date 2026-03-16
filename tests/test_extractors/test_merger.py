"""Tests for Stage 4: Field merger with confidence-weighted selection."""

from docforge.extractors.merger import FieldMerger, merge_fields
from docforge.models.fields import ExtractedFields, FieldValue, empty_fields


class TestFieldMerger:
    """Test confidence-weighted field merging."""

    def test_single_source(self):
        metadata = empty_fields()
        metadata.title = FieldValue(value="Test Title", confidence=0.6,
                                     source="metadata", extraction_method="pdf_info")

        merged = merge_fields(metadata, None, None)
        assert merged.title.value == "Test Title"
        assert merged.title.confidence == 0.6

    def test_highest_confidence_wins(self):
        metadata = empty_fields()
        metadata.title = FieldValue(value="Meta Title", confidence=0.5,
                                     source="metadata", extraction_method="pdf_info")
        heuristic = empty_fields()
        heuristic.title = FieldValue(value="Heuristic Title", confidence=0.8,
                                      source="heuristic", extraction_method="largest_font")

        merged = merge_fields(metadata, None, heuristic)
        assert merged.title.value == "Heuristic Title"

    def test_cross_validation_boost(self):
        metadata = empty_fields()
        metadata.organization = FieldValue(value="DNV", confidence=0.7,
                                            source="metadata", extraction_method="m")
        heuristic = empty_fields()
        heuristic.organization = FieldValue(value="DNV", confidence=0.8,
                                             source="heuristic", extraction_method="h")

        merged = merge_fields(metadata, None, heuristic)
        # Cross-validation should boost above 0.8
        assert merged.organization.confidence > 0.8
        assert merged.organization.value == "DNV"

    def test_no_cross_validation_on_disagreement(self):
        metadata = empty_fields()
        metadata.organization = FieldValue(value="DNV", confidence=0.7,
                                            source="metadata", extraction_method="m")
        heuristic = empty_fields()
        heuristic.organization = FieldValue(value="ABS", confidence=0.8,
                                             source="heuristic", extraction_method="h")

        merged = merge_fields(metadata, None, heuristic)
        assert merged.organization.value == "ABS"
        assert merged.organization.confidence == 0.8  # No boost

    def test_all_empty_sources(self):
        merged = merge_fields(empty_fields(), None, None)
        assert merged.title.is_empty()
        assert merged.author.is_empty()

    def test_merger_stage_processor(self, sample_record):
        """Test the FieldMerger as a stage processor."""
        merger = FieldMerger()
        # sample_record already has merged_fields set; reset for testing
        sample_record.metadata_fields = sample_record.merged_fields
        sample_record.heuristic_fields = None
        sample_record.vlm_fields = None
        merger.process(sample_record)
        assert sample_record.merged_fields is not None
