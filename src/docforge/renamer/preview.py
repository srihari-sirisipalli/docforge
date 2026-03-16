"""
DocForge — Rename Preview
============================

Generates a dry-run preview table showing what would be renamed.
Supports Rich terminal output and data export for Excel/CSV.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from docforge.infra.logging import get_logger
from docforge.storage.database import StateDB

logger = get_logger(__name__)
console = Console()


class RenamePreview:
    """Generates and displays rename preview tables."""

    def __init__(self, db: StateDB):
        self.db = db

    def show(self, limit: int = 0) -> None:
        """Display a rename preview in the terminal using Rich tables.

        Args:
            limit: Maximum rows to show (0 = all).
        """
        records = self.db.get_completed_records()
        if not records:
            console.print("[yellow]No completed documents to preview.[/yellow]")
            return

        table = Table(
            title="DocForge Rename Preview",
            show_lines=True,
            title_style="bold cyan",
        )

        table.add_column("#", style="dim", width=5)
        table.add_column("Original", style="white", max_width=30)
        table.add_column("New Name", style="green", max_width=40)
        table.add_column("Conf", style="yellow", width=6)
        table.add_column("Via", style="cyan", width=8)
        table.add_column("Type", style="magenta", max_width=20)

        shown = 0
        for i, rec in enumerate(records, 1):
            if limit and shown >= limit:
                break

            original = Path(rec["original_path"]).name
            new_name = rec["canonical_name"] or "(no name)"
            strategy = rec["extraction_strategy"] or "unknown"

            # Compute average confidence from merged fields
            conf = _avg_confidence(rec.get("merged_fields", "{}"))
            via = _strategy_label(strategy)

            # Get document type from merged fields
            doc_type = _get_doc_type(rec.get("merged_fields", "{}"))

            table.add_row(
                str(i),
                original,
                new_name,
                f"{conf:.2f}",
                via,
                doc_type,
            )
            shown += 1

        # Summary
        strategies = {}
        for rec in records:
            s = _strategy_label(rec.get("extraction_strategy", ""))
            strategies[s] = strategies.get(s, 0) + 1

        console.print(table)
        console.print()

        summary_parts = [f"Total: [bold]{len(records)}[/bold]"]
        for via, count in sorted(strategies.items()):
            summary_parts.append(f"{via}: {count}")
        console.print(" | ".join(summary_parts))

    def get_preview_data(self) -> list[dict]:
        """Get preview data as a list of dicts (for Excel/CSV export).

        Returns:
            List of dicts with keys matching the Excel export columns.
        """
        records = self.db.get_completed_records()
        preview: list[dict] = []

        for rec in records:
            merged = _parse_fields(rec.get("merged_fields", "{}"))

            preview.append({
                "original_file": Path(rec["original_path"]).name,
                "original_location": rec["original_path"],
                "renamed_file": rec["canonical_name"] or "",
                "moved_to_location": rec.get("target_dir", ""),
                "document_type": merged.get("maritime_document_type", {}).get("value", ""),
                "organization": merged.get("organization", {}).get("value", ""),
                "author": merged.get("author", {}).get("value", ""),
                "date": merged.get("date", {}).get("value", ""),
                "confidence": _avg_confidence_from_parsed(merged),
                "extraction_method": _strategy_label(rec.get("extraction_strategy", "")),
                "status": rec.get("status", ""),
            })

        return preview


def _avg_confidence(merged_json: str) -> float:
    """Compute average confidence from a merged_fields JSON string."""
    return _avg_confidence_from_parsed(_parse_fields(merged_json))


def _avg_confidence_from_parsed(merged: dict) -> float:
    """Compute average confidence from parsed merged fields."""
    confidences = []
    for key, val in merged.items():
        if isinstance(val, dict) and "confidence" in val:
            conf = val["confidence"]
            if conf and conf > 0:
                confidences.append(conf)
    return sum(confidences) / max(len(confidences), 1)


def _strategy_label(strategy: str) -> str:
    """Convert strategy name to a short display label."""
    labels = {
        "vlm_only": "VLM",
        "vlm_plus_heuristic": "VLM+H",
        "text_heuristic": "Heur",
        "text_heuristic_fallback": "Heur*",
        "ocr_heuristic": "OCR",
        "ocr_heuristic_fallback": "OCR*",
        "metadata_only": "Meta",
        "fallback_pending": "Pend",
    }
    return labels.get(strategy, strategy[:6] if strategy else "?")


def _get_doc_type(merged_json: str) -> str:
    """Extract document type from merged fields JSON."""
    merged = _parse_fields(merged_json)
    dt = merged.get("maritime_document_type", {}).get("value", "")
    if dt:
        return dt.replace("_", " ")
    return merged.get("document_type", {}).get("value", "other")


def _parse_fields(json_str: str) -> dict:
    """Safely parse a JSON string."""
    try:
        return json.loads(json_str) if json_str else {}
    except (json.JSONDecodeError, TypeError):
        return {}
