"""
DocForge — CLI: scan command
===============================

Scans a directory for PDF files and registers them in the state database.
This is a lightweight operation — no extraction or processing happens here.
"""

from __future__ import annotations

import click

from docforge.infra.config import load_config
from docforge.infra.logging import setup_logging
from docforge.reporting.formatters import console, print_banner, print_scan_summary
from docforge.scanner import DirectoryScanner
from docforge.storage.database import StateDB


def run_scan(ctx: click.Context, source: str, recursive: bool) -> None:
    """Execute the scan subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    print_banner()
    console.print(f"[bold]Scanning:[/bold] {source}\n")

    # Override recursive setting from CLI
    config.scanner.recursive = recursive

    # Scan
    scanner = DirectoryScanner(config.scanner)
    pending = scanner.scan(source)

    if not pending:
        console.print("[yellow]No PDF files found.[/yellow]")
        return

    # Register in database
    db = StateDB(config.general.db_path)
    inserted = db.insert_pending_documents(pending)
    total = db.get_total_count()
    db.close()

    print_scan_summary(total, source)

    console.print(
        f"  [dim]New: {inserted} | Already registered: {len(pending) - inserted}[/dim]"
    )
    console.print(
        f"\n[dim]Run 'docforge process {source}' to extract metadata.[/dim]\n"
    )
