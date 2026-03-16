"""Tests for filename sanitization."""

from docforge.naming.sanitizer import sanitise_filename


class TestSanitiseFilename:
    """Test filename sanitization for filesystem safety."""

    def test_basic_sanitisation(self):
        result = sanitise_filename("Hello World Test")
        assert " " not in result or "_" in result

    def test_remove_illegal_chars(self):
        result = sanitise_filename("file<>:\"/\\|?*name")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result

    def test_collapse_separators(self):
        result = sanitise_filename("a___b___c", separator="_")
        assert "___" not in result

    def test_max_length(self):
        long_name = "a" * 200
        result = sanitise_filename(long_name, max_length=50)
        assert len(result) <= 50

    def test_lowercase(self):
        result = sanitise_filename("UPPER Case", lowercase=True)
        assert result == result.lower()

    def test_strip_accents(self):
        result = sanitise_filename("café résumé naïve", strip_accents=True)
        assert "é" not in result
        assert "ï" not in result

    def test_windows_reserved_names(self):
        result = sanitise_filename("CON")
        assert result != "CON" and result != "con"

    def test_empty_input(self):
        result = sanitise_filename("")
        assert result == ""  # Empty input returns empty string
