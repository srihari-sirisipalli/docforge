"""
DocForge — CLI: rollback command
===================================

Undo file rename/move operations for a specific job.
Operations are reversed in reverse order using the transaction log.
"""

from __future__ import annotations

import click

from docforge.infra.config import load_config
from docforge.infra.logging import setup_logging
from docforge.reporting.formatters import console, print_banner
from docforge.storage.database import StateDB
from docforge.storage.transactions import TransactionManager


def run_rollback(ctx: click.Context, job: str | None, confirm: bool) -> None:
    """Execute the rollback subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    print_banner()

    db = StateDB(config.general.db_path)

    # Find the target job
    job_id = job or db.get_latest_job_id()

    if not job_id:
        console.print("[yellow]No jobs found in the database.[/yellow]")
        db.close()
        return

    # Check what operations exist
    operations = db.get_executed_operations(job_id, order="DESC")

    if not operations:
        console.print(
            f"[yellow]No executed operations found for job {job_id}.[/yellow]"
        )
        db.close()
        return

    console.print(f"[bold]Rollback job:[/bold] {job_id}")
    console.print(f"[bold]Operations to undo:[/bold] {len(operations)}\n")

    # Show what will be undone
    for op in operations[:10]:
        console.print(
            f"  [dim]{op['operation']}:[/dim] "
            f"{op.get('target_path', '')} → {op.get('source_path', '')}"
        )
    if len(operations) > 10:
        console.print(f"  [dim]... and {len(operations) - 10} more[/dim]")

    # Confirm
    if not confirm:
        if not click.confirm("\nUndo these operations?", default=False):
            console.print("[yellow]Aborted.[/yellow]")
            db.close()
            return

    # Execute rollback
    txn = TransactionManager(db)
    success = txn.rollback_job(job_id)

    if success:
        console.print(
            f"\n[bold green]Rollback complete:[/bold green] "
            f"{len(operations)} operations reversed."
        )
    else:
        console.print(
            "\n[bold red]Rollback failed.[/bold red] "
            "Check logs for details."
        )

    db.close()
