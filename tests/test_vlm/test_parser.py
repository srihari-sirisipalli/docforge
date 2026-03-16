"""Tests for VLM response parsing."""

from docforge.vlm.parser import parse_vlm_response


class TestVLMResponseParser:
    """Test parsing of VLM JSON responses."""

    def test_clean_json(self):
        response = '{"title": "Test Report", "author": "John Smith", "organization": "DNV"}'
        fields = parse_vlm_response(response, "minicpm-v")

        assert fields.title.value == "Test Report"
        assert fields.author.value == "John Smith"
        assert fields.organization.value == "DNV"

    def test_markdown_fenced_json(self):
        response = '```json\n{"title": "Test Report", "author": null}\n```'
        fields = parse_vlm_response(response, "minicpm-v")

        assert fields.title.value == "Test Report"
        assert fields.author.is_empty()

    def test_null_values_handled(self):
        response = '{"title": null, "author": null, "date": null}'
        fields = parse_vlm_response(response, "test")

        assert fields.title.is_empty()
        assert fields.author.is_empty()

    def test_empty_response(self):
        fields = parse_vlm_response("", "test")
        assert fields.title.is_empty()

    def test_invalid_json(self):
        fields = parse_vlm_response("not json at all", "test")
        assert fields.title.is_empty()

    def test_partial_json(self):
        response = '{"title": "Report", "organization": "IMO"}'
        fields = parse_vlm_response(response, "test")

        assert fields.title.value == "Report"
        assert fields.organization.value == "IMO"
