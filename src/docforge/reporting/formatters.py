"""
DocForge — Terminal Output Formatters
=======================================

Rich-based terminal output for progress display, status panels,
and summary tables. Used by the CLI to show informative, structured
processing output.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

console = Console()


def print_banner() -> None:
    """Print the DocForge startup banner."""
    console.print(Panel(
        "[bold cyan]DocForge[/bold cyan] v1.0 — Offline Document Intelligence\n"
        "[dim]Smart PDF Processing, Classification & Organisation System[/dim]",
        border_style="cyan",
    ))


def print_system_profile(profile) -> None:
    """Print system hardware profile summary."""
    table = Table(title="System Profile", show_header=False, border_style="dim")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("CPU", f"{profile.cpu_cores} cores ({profile.cpu_name})")
    table.add_row("RAM", f"{profile.total_ram_gb:.1f} GB total, {profile.available_ram_gb:.1f} GB available")
    table.add_row("GPU", profile.gpu_name or "Not detected")
    table.add_row("VLM Capable", "Yes" if profile.can_run_vlm else "No")
    table.add_row("Recommended VLM", profile.recommended_vlm or "N/A (insufficient RAM)")
    table.add_row("OS", profile.os_name)
    table.add_row("Python", profile.python_version)

    console.print(table)
    console.print()


def print_processing_config(config, profile) -> None:
    """Print the processing configuration summary."""
    console.print(Panel(
        f"[bold]Processing Configuration[/bold]\n"
        f"  VLM: {'[green]Enabled[/green]' if config.vlm.enabled else '[red]Disabled[/red]'}"
        f" — {config.vlm.model} via {config.vlm.runtime}\n"
        f"  OCR Fallback: {'[green]Enabled[/green]' if config.ocr.enabled else '[dim]Disabled[/dim]'}\n"
        f"  Workers: {config.performance.max_workers or profile.recommended_workers} "
        f"(VLM: {config.performance.vlm_concurrent})\n"
        f"  Strategy: {config.organizer.strategy}\n"
        f"  Safety: {'[yellow]Dry Run[/yellow]' if config.safety.dry_run else '[green]Execute[/green]'}",
        border_style="blue",
    ))


def print_scan_summary(total: int, source: str) -> None:
    """Print scan results summary."""
    console.print(
        f"\n[bold green]Scan complete:[/bold green] "
        f"[bold]{total:,}[/bold] PDF files found in [cyan]{source}[/cyan]\n"
    )


def print_final_stats(stats: dict) -> None:
    """Print final processing statistics."""
    table = Table(title="Processing Results", border_style="green")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold white")

    table.add_row("Total documents", f"{stats.get('total', 0):,}")
    table.add_row("Completed", f"[green]{stats.get('complete', 0):,}[/green]")
    table.add_row("Errors", f"[red]{stats.get('errors', 0):,}[/red]")
    table.add_row("Skipped", f"{stats.get('skipped', 0):,}")

    if stats.get("strategies"):
        table.add_row("", "")
        for strategy, count in sorted(stats["strategies"].items()):
            table.add_row(f"  via {strategy}", str(count))

    if stats.get("avg_processing_ms"):
        table.add_row("Avg time/doc", f"{stats['avg_processing_ms']:.0f} ms")

    console.print(table)
    console.print()


def create_progress() -> Progress:
    """Create a Rich progress bar for processing."""
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        TextColumn("[dim]|[/dim]"),
        TimeRemainingColumn(),
        console=console,
    )


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]Success:[/bold green] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")
