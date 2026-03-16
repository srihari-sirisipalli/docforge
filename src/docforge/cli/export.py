"""
DocForge — CLI: export command
=================================

Export processing results to Excel, JSON, CSV, or Markdown format.
Supports exporting all formats at once with --format all.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from docforge.infra.config import load_config
from docforge.infra.logging import setup_logging
from docforge.reporting.exporters import (
    CSVExporter,
    ExcelExporter,
    JSONExporter,
    MarkdownReporter,
)
from docforge.reporting.formatters import console, print_banner
from docforge.storage.database import StateDB


# Map format names to (exporter_class, default_extension)
EXPORTERS = {
    "excel":    (ExcelExporter,     ".xlsx"),
    "json":     (JSONExporter,      ".json"),
    "csv":      (CSVExporter,       ".csv"),
    "markdown": (MarkdownReporter,  ".md"),
}


def run_export(ctx: click.Context, fmt: str, output: str | None) -> None:
    """Execute the export subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    print_banner()

    db = StateDB(config.general.db_path)
    total = db.get_total_count()

    if total == 0:
        console.print("[yellow]No documents in the database. Run 'docforge process' first.[/yellow]")
        db.close()
        return

    stats = db.get_progress_stats()
    console.print(
        f"[bold]Database:[/bold] {total} documents "
        f"({stats.get('complete', 0)} complete, "
        f"{stats.get('errors', 0)} errors)\n"
    )

    # Determine which formats to export
    formats = list(EXPORTERS.keys()) if fmt == "all" else [fmt]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for format_name in formats:
        exporter_cls, ext = EXPORTERS[format_name]

        # Build output path
        if output and fmt != "all":
            out_path = output
        else:
            out_path = f"docforge_results_{timestamp}{ext}"

        exporter = exporter_cls()
        result_path = exporter.export(db, out_path)

        console.print(
            f"  [green]Exported:[/green] {format_name.upper()} → {result_path}"
        )

    console.print()
    db.close()
