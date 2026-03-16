"""Tests for folder organisation strategies."""

from docforge.models.fields import FieldValue, empty_fields
from docforge.organizer.strategies import get_strategy
from docforge.organizer.tree_builder import FolderOrganizer


class TestStrategies:
    """Test individual organisation strategy functions."""

    def test_year_strategy(self):
        fn = get_strategy("year")
        fields = empty_fields()
        fields.year = FieldValue(value="2023", confidence=0.8,
                                  source="h", extraction_method="m")
        path = fn(fields)
        assert "2023" in path

    def test_type_strategy(self):
        fn = get_strategy("type")
        fields = empty_fields()
        fields.document_type = FieldValue(value="report", confidence=0.8,
                                           source="h", extraction_method="m")
        path = fn(fields)
        assert len(path) > 0

    def test_domain_type_strategy(self):
        fn = get_strategy("domain_type")
        fields = empty_fields()
        fields.document_type = FieldValue(value="invoice", confidence=0.8,
                                           source="h", extraction_method="m")
        path = fn(fields)
        assert "financial" in path.lower()

    def test_domain_type_certificate(self):
        fn = get_strategy("domain_type")
        fields = empty_fields()
        fields.document_type = FieldValue(value="certificate", confidence=0.8,
                                           source="h", extraction_method="m")
        path = fn(fields)
        assert "academic" in path.lower()


class TestFolderOrganizer:
    """Test the FolderOrganizer wrapper."""

    def test_compute_target(self, tmp_path, sample_fields):
        organizer = FolderOrganizer(
            strategy="type",
            base_dir=str(tmp_path / "organized"),
        )
        target = organizer.compute_target(sample_fields, "report_2023.pdf")
        assert target.endswith("report_2023.pdf")
        assert "organized" in target

    def test_compute_target_dir(self, tmp_path, sample_fields):
        organizer = FolderOrganizer(
            strategy="type",
            base_dir=str(tmp_path / "organized"),
        )
        target_dir = organizer.compute_target_dir(sample_fields)
        assert "organized" in target_dir
