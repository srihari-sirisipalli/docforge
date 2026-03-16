"""Tests for Stage 5: Filename generation from templates."""

from docforge.infra.config import NamingConfig
from docforge.models.fields import FieldValue, empty_fields
from docforge.naming.generator import FilenameGenerator


class TestFilenameGenerator:
    """Test canonical filename generation."""

    def test_basic_generation(self, sample_fields):
        config = NamingConfig()
        gen = FilenameGenerator(config)
        filename = gen.generate(sample_fields, file_id="abc123")

        assert filename.endswith(".pdf")
        assert "dnv" in filename.lower()
        assert len(filename) <= config.max_length

    def test_empty_fields_fallback(self):
        config = NamingConfig()
        gen = FilenameGenerator(config)
        fields = empty_fields()
        filename = gen.generate(fields, file_id="abc123def456")

        assert filename.endswith(".pdf")
        # Should use file_id fallback
        assert "abc123" in filename

    def test_max_length_enforced(self, sample_fields):
        config = NamingConfig(max_length=40)
        gen = FilenameGenerator(config)
        filename = gen.generate(sample_fields, file_id="abc")

        assert len(filename) <= 40

    def test_lowercase(self, sample_fields):
        config = NamingConfig(lowercase=True)
        gen = FilenameGenerator(config)
        filename = gen.generate(sample_fields, file_id="abc")

        assert filename == filename.lower()

    def test_custom_template(self):
        config = NamingConfig()
        gen = FilenameGenerator(config)
        fields = empty_fields()
        fields.organization = FieldValue(value="IMO", confidence=0.9,
                                          source="h", extraction_method="m")
        fields.year = FieldValue(value="2024", confidence=0.8,
                                  source="h", extraction_method="m")

        filename = gen.generate(fields, file_id="abc", template="{org}_{year}")
        assert "imo" in filename.lower()
        assert "2024" in filename
