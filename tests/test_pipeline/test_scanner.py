"""Tests for the directory scanner."""

import pytest

from docforge.scanner import DirectoryScanner


class TestDirectoryScanner:
    """Test PDF file discovery."""

    def test_scan_directory(self, multiple_pdfs, tmp_path):
        scanner = DirectoryScanner()
        results = scanner.scan(str(tmp_path))

        assert len(results) == 5
        assert all(r.file_size_bytes > 0 for r in results)
        assert all(r.file_id for r in results)

    def test_scan_single_file(self, mock_pdf):
        scanner = DirectoryScanner()
        results = scanner.scan(mock_pdf)

        assert len(results) == 1
        assert results[0].original_path == mock_pdf

    def test_scan_nonexistent(self):
        scanner = DirectoryScanner()
        results = scanner.scan("/nonexistent/path")
        assert len(results) == 0

    def test_scan_empty_directory(self, tmp_path):
        scanner = DirectoryScanner()
        results = scanner.scan(str(tmp_path))
        assert len(results) == 0

    def test_deduplication(self, mock_pdf, tmp_path):
        """Same file content should produce same file_id."""
        import shutil
        copy_path = str(tmp_path / "copy.pdf")
        shutil.copy2(mock_pdf, copy_path)

        scanner = DirectoryScanner()
        results = scanner.scan(str(tmp_path))

        # Both files have same content → same file_id → deduped to 1
        file_ids = [r.file_id for r in results]
        assert len(set(file_ids)) == len(results)

    def test_non_recursive(self, tmp_path, mock_pdf):
        import shutil
        from docforge.infra.config import ScannerConfig

        # Create a nested directory with a PDF
        sub = tmp_path / "subdir"
        sub.mkdir()
        shutil.copy2(mock_pdf, str(sub / "nested.pdf"))
        shutil.copy2(mock_pdf, str(tmp_path / "top.pdf"))

        scanner = DirectoryScanner(ScannerConfig(recursive=False))
        results = scanner.scan(str(tmp_path))

        # Should only find the top-level PDF
        assert len(results) == 1
