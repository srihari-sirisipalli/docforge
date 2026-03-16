"""Tests for export functionality (JSON, CSV, Markdown)."""

import json
from pathlib import Path

from docforge.reporting.exporters import CSVExporter, JSONExporter, MarkdownReporter
from docforge.storage.database import StateDB


class TestJSONExporter:
    """Test JSON export."""

    def test_export_empty_db(self, db, tmp_path):
        exporter = JSONExporter()
        output = str(tmp_path / "test.json")
        exporter.export(db, output)

        with open(output) as f:
            data = json.load(f)
        assert data["total_documents"] == 0
        assert data["documents"] == []

    def test_export_creates_file(self, db, tmp_path):
        exporter = JSONExporter()
        output = str(tmp_path / "subdir" / "test.json")
        result = exporter.export(db, output)
        assert Path(result).exists()


class TestCSVExporter:
    """Test CSV export."""

    def test_export_empty_db(self, db, tmp_path):
        exporter = CSVExporter()
        output = str(tmp_path / "test.csv")
        result = exporter.export(db, output)
        assert Path(result).exists()


class TestMarkdownReporter:
    """Test Markdown report generation."""

    def test_export_empty_db(self, db, tmp_path):
        exporter = MarkdownReporter()
        output = str(tmp_path / "test.md")
        result = exporter.export(db, output)
        assert Path(result).exists()

        content = Path(result).read_text()
        assert "# DocForge Processing Report" in content
