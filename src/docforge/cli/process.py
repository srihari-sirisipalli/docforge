"""
DocForge — CLI: process command
==================================

The main processing command. Runs the full pipeline:
scan → extract → classify → merge → name → (optionally) rename.
"""

from __future__ import annotations

import click
import fitz  # PyMuPDF

from docforge.infra.config import load_config
from docforge.infra.hardware import profile_system
from docforge.infra.logging import setup_logging
from docforge.pipeline.orchestrator import PipelineOrchestrator
from docforge.reporting.formatters import console, print_banner


def run_process(
    ctx: click.Context,
    source: str,
    vlm: bool,
    model: str | None,
    runtime: str | None,
    workers: int,
    execute: bool,
) -> None:
    """Execute the process subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    # Apply CLI overrides
    config.vlm.enabled = vlm
    if model:
        config.vlm.model = model
    if runtime:
        config.vlm.runtime = runtime
    if workers > 0:
        config.performance.max_workers = workers
    config.safety.dry_run = not execute

    # Suppress MuPDF internal warnings (malformed structure trees, etc.)
    fitz.TOOLS.mupdf_warnings(False)

    print_banner()

    # Profile hardware
    profile = profile_system(target_path=source)

    # Run pipeline
    orchestrator = PipelineOrchestrator(config, profile)
    stats = orchestrator.run(source)

    # Offer next steps
    if stats.get("complete", 0) > 0:
        console.print("[bold]Next steps:[/bold]")
        console.print("  docforge rename          — Preview file renames")
        console.print("  docforge rename --execute — Apply renames")
        console.print("  docforge export -f excel  — Export results to Excel")
        console.print()

    if execute and stats.get("complete", 0) > 0:
        console.print("[dim]Renames were applied (--execute flag was set).[/dim]\n")
