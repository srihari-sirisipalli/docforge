"""
DocForge — CLI Entry Point
=============================

Main Click group that registers all subcommands. This module is the
entry point configured in pyproject.toml:
    [project.scripts]
    docforge = "docforge.cli.main:cli"

Usage:
    docforge --help
    docforge scan /path/to/pdfs
    docforge process /path/to/pdfs --vlm --execute
"""

from __future__ import annotations

import click

from docforge import __version__
from docforge.reporting.formatters import print_banner


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="DocForge")
@click.option("--config", "-c", type=click.Path(), default=None,
              help="Path to TOML configuration file.")
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Enable verbose (DEBUG) logging.")
@click.option("--quiet", "-q", is_flag=True, default=False,
              help="Suppress non-essential output.")
@click.pass_context
def cli(ctx: click.Context, config: str | None, verbose: bool, quiet: bool):
    """DocForge — Offline Document Intelligence for PDF Collections.

    Process, classify, rename, and organize PDF document collections using
    Vision-Language Models and intelligent heuristics.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet

    if ctx.invoked_subcommand is None:
        print_banner()
        click.echo(ctx.get_help())


# =========================================================================
# Register subcommands (lazy imports to avoid slow startup)
# =========================================================================

@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--recursive/--no-recursive", default=True,
              help="Scan subdirectories recursively.")
@click.pass_context
def scan(ctx, source: str, recursive: bool):
    """Scan a directory for PDF files and register them in the database."""
    from docforge.cli.scan import run_scan
    run_scan(ctx, source, recursive)


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--vlm/--no-vlm", default=True,
              help="Enable Vision-Language Model extraction.")
@click.option("--model", "-m", type=str, default=None,
              help="VLM model name (e.g., minicpm-v, llava, moondream).")
@click.option("--runtime", "-r", type=click.Choice(["ollama", "llamacpp", "transformers"]),
              default=None, help="VLM runtime backend.")
@click.option("--workers", "-w", type=int, default=0,
              help="Number of workers (0=auto).")
@click.option("--execute", is_flag=True, default=False,
              help="Execute renames after processing (default: dry-run).")
@click.pass_context
def process(ctx, source: str, vlm: bool, model: str | None,
            runtime: str | None, workers: int, execute: bool):
    """Process PDFs: extract metadata, classify, and generate names."""
    from docforge.cli.process import run_process
    run_process(ctx, source, vlm, model, runtime, workers, execute)


@cli.command()
@click.option("--execute", is_flag=True, default=False,
              help="Apply renames (default: preview only).")
@click.option("--strategy", "-s",
              type=click.Choice(["suffix", "hash"]), default="suffix",
              help="Collision resolution strategy.")
@click.pass_context
def rename(ctx, execute: bool, strategy: str):
    """Preview or execute file renames based on processing results."""
    from docforge.cli.rename import run_rename
    run_rename(ctx, execute, strategy)


@cli.command()
@click.option("--strategy", "-s", default="type",
              help="Folder organization strategy (year, type, year_type, domain_type, domain_year).")
@click.option("--output", "-o", type=click.Path(), default="./organized/",
              help="Output base directory.")
@click.pass_context
def organize(ctx, strategy: str, output: str):
    """Organize processed files into a structured folder hierarchy."""
    from docforge.cli.organize import run_organize
    run_organize(ctx, strategy, output)


@cli.command()
@click.option("--format", "-f", "fmt",
              type=click.Choice(["excel", "json", "csv", "markdown", "all"]),
              default="excel", help="Export format.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path (auto-generated if not specified).")
@click.pass_context
def export(ctx, fmt: str, output: str | None):
    """Export processing results to Excel, JSON, CSV, or Markdown."""
    from docforge.cli.export import run_export
    run_export(ctx, fmt, output)


@cli.command()
@click.pass_context
def status(ctx):
    """Show current processing progress and statistics."""
    from docforge.cli.status import run_status
    run_status(ctx)


@cli.command()
@click.option("--job", "-j", type=str, default=None,
              help="Job ID to rollback (default: latest).")
@click.option("--confirm", is_flag=True, default=False,
              help="Skip confirmation prompt.")
@click.pass_context
def rollback(ctx, job: str | None, confirm: bool):
    """Undo file rename/move operations for a job."""
    from docforge.cli.rollback import run_rollback
    run_rollback(ctx, job, confirm)


@cli.command()
@click.argument("action", type=click.Choice(["list", "pull", "status"]))
@click.option("--model", "-m", type=str, default=None,
              help="Model name for pull/status operations.")
@click.pass_context
def model(ctx, action: str, model_name: str | None):
    """Manage VLM models (list, pull, check status)."""
    from docforge.cli.model import run_model
    run_model(ctx, action, model_name)


@cli.command()
@click.pass_context
def setup(ctx):
    """First-run setup: check dependencies, configure, download models."""
    from docforge.cli.setup import run_setup
    run_setup(ctx)
