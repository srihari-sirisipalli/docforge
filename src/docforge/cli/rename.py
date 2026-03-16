"""
DocForge — CLI: rename command
=================================

Preview or execute file renames based on processing results.
Default is dry-run (preview only) for safety.
"""

from __future__ import annotations

import click

from docforge.infra.config import load_config
from docforge.infra.logging import setup_logging
from docforge.naming.collision import CollisionResolver
from docforge.organizer.tree_builder import FolderOrganizer
from docforge.renamer.engine import RenameEngine
from docforge.renamer.preview import RenamePreview
from docforge.reporting.formatters import console, print_banner
from docforge.storage.database import StateDB


def run_rename(ctx: click.Context, execute: bool, strategy: str) -> None:
    """Execute the rename subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    print_banner()

    db = StateDB(config.general.db_path)

    # Show preview first
    preview = RenamePreview(db)
    preview.show()

    if not execute:
        console.print(
            "\n[dim]This is a dry run. Add --execute to apply renames.[/dim]\n"
        )
        db.close()
        return

    # Confirm before executing
    if config.safety.require_confirmation:
        if not click.confirm("\nApply these renames?", default=False):
            console.print("[yellow]Aborted.[/yellow]")
            db.close()
            return

    # Setup organizer if enabled
    organizer = None
    if config.organizer.enabled:
        organizer = FolderOrganizer(
            strategy=config.organizer.strategy,
            base_dir=config.organizer.base_dir,
        )

    # Execute renames
    engine = RenameEngine(
        db=db,
        collision_strategy=strategy,
        organizer=organizer,
    )

    job_id = db.get_latest_job_id() or "manual"
    result = engine.execute(job_id=job_id, dry_run=False)

    console.print(
        f"\n[bold]Result:[/bold] {result.get('operations', 0)} operations, "
        f"{result.get('skipped', 0)} skipped, "
        f"{result.get('errors', 0)} errors"
    )

    db.close()
