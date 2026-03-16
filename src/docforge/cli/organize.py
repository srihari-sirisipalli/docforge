"""
DocForge — CLI: organize command
===================================

Organize processed files into a structured folder hierarchy
based on document type, domain, and other metadata.
"""

from __future__ import annotations

import click

from docforge.infra.config import load_config
from docforge.infra.logging import setup_logging
from docforge.organizer.tree_builder import FolderOrganizer
from docforge.renamer.engine import RenameEngine
from docforge.reporting.formatters import console, print_banner
from docforge.storage.database import StateDB


def run_organize(ctx: click.Context, strategy: str, output: str) -> None:
    """Execute the organize subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    print_banner()

    db = StateDB(config.general.db_path)

    # Setup organizer with CLI overrides
    organizer = FolderOrganizer(strategy=strategy, base_dir=output)

    console.print(f"[bold]Organization strategy:[/bold] {strategy}")
    console.print(f"[bold]Output directory:[/bold] {output}")
    console.print()

    # Show what would happen (dry run)
    engine = RenameEngine(
        db=db,
        collision_strategy=config.naming.collision_strategy,
        organizer=organizer,
    )

    job_id = db.get_latest_job_id() or "organize"
    result = engine.execute(job_id=job_id, dry_run=True)

    console.print(
        f"\n[dim]{result.get('operations', 0)} operations planned. "
        f"Use 'docforge rename --execute' to apply.[/dim]\n"
    )

    db.close()
