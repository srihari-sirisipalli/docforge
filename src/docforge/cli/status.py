"""
DocForge — CLI: status command
=================================

Shows current processing progress, statistics, and system status.
"""

from __future__ import annotations

import click

from docforge.infra.config import load_config
from docforge.infra.logging import setup_logging
from docforge.reporting.formatters import console, print_banner, print_final_stats
from docforge.storage.database import StateDB


def run_status(ctx: click.Context) -> None:
    """Execute the status subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    print_banner()

    db = StateDB(config.general.db_path)
    total = db.get_total_count()

    if total == 0:
        console.print("[yellow]No documents in the database.[/yellow]")
        console.print("[dim]Run 'docforge scan <directory>' to get started.[/dim]\n")
        db.close()
        return

    # Show progress stats
    stats = db.get_final_stats()
    print_final_stats(stats)

    # Show latest job info
    job_id = db.get_latest_job_id()
    if job_id:
        console.print(f"[dim]Latest job: {job_id}[/dim]")

    # Show recent errors (if any)
    errors = stats.get("errors", 0)
    if errors > 0:
        console.print(f"\n[bold red]{errors} documents with errors.[/bold red]")
        console.print("[dim]Check logs for details or re-run with --verbose.[/dim]")

    console.print()
    db.close()
