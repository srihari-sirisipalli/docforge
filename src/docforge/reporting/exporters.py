"""
DocForge — Report Exporters
==============================

Exports processing results in multiple formats:
  - Excel (.xlsx) — Primary export with styled headers, auto-width columns
  - JSON — Full metadata dump
  - CSV — Lightweight tabular export
  - Markdown — Human-readable summary report

The Excel export includes these columns:
    A: Original File        — Original filename
    B: Original Location    — Full path before rename
    C: Renamed File         — New canonical filename
    D: Moved To Location    — Full path after rename/move
    E: Document Type        — Maritime document type
    F: Organisation         — Detected organisation
    G: Author               — Detected author
    H: Date                 — Detected date
    I: Confidence           — Average confidence score
    J: Extraction Method    — VLM / Heuristic / OCR / Metadata
    K: Status               — Complete / Error / Skipped
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from docforge.infra.logging import get_logger
from docforge.renamer.preview import RenamePreview
from docforge.storage.database import StateDB

logger = get_logger(__name__)


# =============================================================================
# Excel Exporter
# =============================================================================

class ExcelExporter:
    """Exports processing results to a styled Excel (.xlsx) file.

    Uses openpyxl for formatting: bold headers with blue background,
    auto-fitted column widths, frozen header row, and auto-filter.
    """

    # Column definitions: (header_label, data_key, width_estimate)
    COLUMNS = [
        ("Sr. No.",             "sr_no",              8),
        ("Original File",       "original_file",      35),
        ("Original Location",   "original_location",  50),
        ("Renamed File",        "renamed_file",       40),
        ("Moved To Location",   "moved_to_location",  50),
        ("Document Type",       "document_type",      25),
        ("Organisation",        "organization",       15),
        ("Author",              "author",             20),
        ("Date",                "date",               12),
        ("Confidence",          "confidence",         12),
        ("Extraction Method",   "extraction_method",  18),
        ("Status",              "status",             10),
    ]

    def export(self, db: StateDB, output_path: str) -> str:
        """Export all processing results to an Excel file.

        Args:
            db:          StateDB instance with completed records.
            output_path: Path for the output .xlsx file.

        Returns:
            The output file path.
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError(
                "Excel export requires openpyxl: pip install openpyxl"
            )

        logger.info("Exporting to Excel: %s", output_path)

        # Get data
        preview = RenamePreview(db)
        data = preview.get_preview_data()

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "DocForge Results"

        # ── Header row styling ──────────────────────────────────────────
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for col_idx, (header, _, width) in enumerate(self.COLUMNS, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        # ── Data rows ───────────────────────────────────────────────────
        data_align = Alignment(vertical="top", wrap_text=False)
        conf_format = '0.00'

        for row_idx, record in enumerate(data, 2):
            ws.cell(row=row_idx, column=1, value=row_idx - 1)  # Sr. No.
            ws.cell(row=row_idx, column=2, value=record.get("original_file", ""))
            ws.cell(row=row_idx, column=3, value=record.get("original_location", ""))
            ws.cell(row=row_idx, column=4, value=record.get("renamed_file", ""))
            ws.cell(row=row_idx, column=5, value=record.get("moved_to_location", ""))
            ws.cell(row=row_idx, column=6, value=_format_doc_type(record.get("document_type", "")))
            ws.cell(row=row_idx, column=7, value=record.get("organization", ""))
            ws.cell(row=row_idx, column=8, value=record.get("author", ""))
            ws.cell(row=row_idx, column=9, value=record.get("date", ""))

            conf_cell = ws.cell(row=row_idx, column=10, value=record.get("confidence", 0))
            conf_cell.number_format = conf_format

            ws.cell(row=row_idx, column=11, value=record.get("extraction_method", ""))

            status_cell = ws.cell(row=row_idx, column=12, value=record.get("status", ""))
            # Colour-code status
            if record.get("status") == "complete":
                status_cell.font = Font(color="006600")
            elif record.get("status") == "error":
                status_cell.font = Font(color="CC0000")

            # Apply alignment to all cells in this row
            for col in range(1, len(self.COLUMNS) + 1):
                ws.cell(row=row_idx, column=col).alignment = data_align

        # ── Summary row ─────────────────────────────────────────────────
        summary_row = len(data) + 3
        ws.cell(row=summary_row, column=1, value="SUMMARY").font = Font(bold=True)
        ws.cell(row=summary_row + 1, column=1, value="Total Documents")
        ws.cell(row=summary_row + 1, column=2, value=len(data))

        # Count by method
        method_counts: dict[str, int] = {}
        for rec in data:
            m = rec.get("extraction_method", "Unknown")
            method_counts[m] = method_counts.get(m, 0) + 1

        row = summary_row + 2
        for method, count in sorted(method_counts.items()):
            ws.cell(row=row, column=1, value=f"  {method}")
            ws.cell(row=row, column=2, value=count)
            row += 1

        # Average confidence
        confidences = [r["confidence"] for r in data if r.get("confidence", 0) > 0]
        avg_conf = sum(confidences) / max(len(confidences), 1)
        ws.cell(row=row, column=1, value="Average Confidence")
        ws.cell(row=row, column=2, value=round(avg_conf, 3))

        # ── Freeze top row and add auto-filter ──────────────────────────
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        # ── Save ────────────────────────────────────────────────────────
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        logger.info("Excel export complete: %s (%d records)", output_path, len(data))

        return output_path


# =============================================================================
# JSON Exporter
# =============================================================================

class JSONExporter:
    """Exports all metadata as a JSON file."""

    def export(self, db: StateDB, output_path: str) -> str:
        preview = RenamePreview(db)
        data = preview.get_preview_data()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "exported_at": datetime.now().isoformat(),
                "total_documents": len(data),
                "documents": data,
            }, f, indent=2, default=str)

        logger.info("JSON export complete: %s (%d records)", output_path, len(data))
        return output_path


# =============================================================================
# CSV Exporter
# =============================================================================

class CSVExporter:
    """Exports processing results as a CSV file."""

    def export(self, db: StateDB, output_path: str) -> str:
        preview = RenamePreview(db)
        data = preview.get_preview_data()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            if not data:
                return output_path

            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

        logger.info("CSV export complete: %s (%d records)", output_path, len(data))
        return output_path


# =============================================================================
# Markdown Report
# =============================================================================

class MarkdownReporter:
    """Generates a processing summary report in Markdown."""

    def export(self, db: StateDB, output_path: str) -> str:
        stats = db.get_final_stats()
        preview = RenamePreview(db)
        data = preview.get_preview_data()

        lines = [
            "# DocForge Processing Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total documents | {stats.get('total', 0)} |",
            f"| Completed | {stats.get('complete', 0)} |",
            f"| Errors | {stats.get('errors', 0)} |",
            f"| Skipped | {stats.get('skipped', 0)} |",
            "",
            "## Strategy Breakdown",
            "",
            "| Strategy | Count |",
            "|----------|-------|",
        ]

        for strategy, count in sorted(stats.get("strategies", {}).items()):
            lines.append(f"| {strategy} | {count} |")

        lines.extend([
            "",
            "## Sample Results (first 20)",
            "",
            "| Original | Renamed | Type | Conf |",
            "|----------|---------|------|------|",
        ])

        for rec in data[:20]:
            lines.append(
                f"| {rec.get('original_file', '')[:30]} "
                f"| {rec.get('renamed_file', '')[:35]} "
                f"| {_format_doc_type(rec.get('document_type', ''))[:20]} "
                f"| {rec.get('confidence', 0):.2f} |"
            )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("Markdown report: %s", output_path)
        return output_path


# =============================================================================
# Helpers
# =============================================================================

def _format_doc_type(doc_type: str) -> str:
    """Format document type for display (replace underscores with spaces)."""
    if not doc_type:
        return "Other"
    return doc_type.replace("_", " ").title()
