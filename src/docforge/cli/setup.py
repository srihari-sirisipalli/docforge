"""
DocForge — CLI: setup command (First-Run Wizard)
===================================================

Guides the user through initial setup:
  1. Check Python version and dependencies
  2. Detect system hardware
  3. Generate default configuration
  4. Check/install Ollama (optional)
  5. Pull recommended VLM model (optional)
  6. Verify Tesseract OCR (optional)
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys

import click

from docforge.infra.config import RuntimeConfig, save_config
from docforge.infra.hardware import (
    check_ollama_installed,
    check_tesseract_installed,
    get_tesseract_path,
    profile_system,
)
from docforge.infra.logging import setup_logging
from docforge.reporting.formatters import console, print_banner, print_system_profile


def run_setup(ctx: click.Context) -> None:
    """Execute the first-run setup wizard."""
    setup_logging("INFO", "~/.docforge/logs/")
    print_banner()

    console.print("[bold cyan]First-Run Setup Wizard[/bold cyan]\n")

    # ── Step 1: Python version ───────────────────────────────────────────
    py_version = sys.version_info
    console.print(f"[bold]Step 1:[/bold] Python version check")
    console.print(f"  Python {py_version.major}.{py_version.minor}.{py_version.micro}")

    if py_version < (3, 10):
        console.print(
            "  [red]DocForge requires Python 3.10+. "
            "Please upgrade your Python installation.[/red]\n"
        )
        return

    console.print("  [green]OK[/green]\n")

    # ── Step 2: Core dependencies ────────────────────────────────────────
    console.print("[bold]Step 2:[/bold] Checking core dependencies")
    _check_dependency("PyMuPDF (fitz)", "fitz")
    _check_dependency("Click", "click")
    _check_dependency("Rich", "rich")
    _check_dependency("Pillow", "PIL")
    _check_dependency("psutil", "psutil")
    _check_dependency("python-dateutil", "dateutil")
    _check_dependency("unidecode", "unidecode")
    console.print()

    # ── Step 3: Optional dependencies ────────────────────────────────────
    console.print("[bold]Step 3:[/bold] Checking optional dependencies")
    _check_dependency("openpyxl (Excel export)", "openpyxl", required=False)
    _check_dependency("requests (model download)", "requests", required=False)
    console.print()

    # ── Step 4: System profiling ─────────────────────────────────────────
    console.print("[bold]Step 4:[/bold] System hardware profile")
    profile = profile_system()
    print_system_profile(profile)

    # ── Step 5: Ollama check ─────────────────────────────────────────────
    console.print("[bold]Step 5:[/bold] VLM Runtime (Ollama)")

    if check_ollama_installed():
        console.print("  [green]Ollama is installed[/green]")

        if profile.can_run_vlm:
            console.print(
                f"  Recommended model: [bold]{profile.recommended_vlm}[/bold]"
            )
            if click.confirm(
                f"  Pull '{profile.recommended_vlm}' now?", default=True
            ):
                _pull_ollama_model(profile.recommended_vlm)
        else:
            console.print(
                "  [yellow]Insufficient RAM for VLM. "
                "DocForge will use heuristic extraction.[/yellow]"
            )
    else:
        console.print("  [yellow]Ollama not installed (optional)[/yellow]")
        console.print("  Install from: https://ollama.ai")
        console.print(
            "  [dim]Without Ollama, DocForge uses text heuristics + OCR.[/dim]"
        )

    console.print()

    # ── Step 6: Tesseract check ──────────────────────────────────────────
    console.print("[bold]Step 6:[/bold] OCR Engine (Tesseract)")

    if check_tesseract_installed():
        tess_path = get_tesseract_path()
        console.print(f"  [green]Tesseract is installed[/green] ({tess_path})")
    else:
        console.print("  [yellow]Tesseract not installed (optional)[/yellow]")
        if platform.system() == "Windows":
            console.print(
                "  Install: https://github.com/UB-Mannheim/tesseract/wiki"
            )
        elif platform.system() == "Linux":
            console.print("  Install: sudo apt install tesseract-ocr")
        elif platform.system() == "Darwin":
            console.print("  Install: brew install tesseract")

    console.print()

    # ── Step 7: Generate config ──────────────────────────────────────────
    console.print("[bold]Step 7:[/bold] Generate configuration")

    config = RuntimeConfig()

    # Auto-tune based on hardware
    if profile.recommended_vlm:
        config.vlm.model = profile.recommended_vlm
    else:
        config.vlm.enabled = False

    config.performance.max_workers = profile.recommended_workers
    config.vlm.threads = profile.recommended_vlm_threads

    if profile.gpu_available and profile.gpu_vram_gb >= 4:
        config.vlm.gpu_layers = 35  # Offload to GPU

    config_path = save_config(config)
    console.print(f"  Configuration saved: [cyan]{config_path}[/cyan]")
    console.print()

    # ── Summary ──────────────────────────────────────────────────────────
    console.print("[bold green]Setup complete![/bold green]\n")
    console.print("[bold]Quick start:[/bold]")
    console.print("  1. Place your PDFs in a directory")
    console.print("  2. docforge process /path/to/pdfs")
    console.print("  3. docforge rename --execute")
    console.print("  4. docforge export -f excel")
    console.print()


def _check_dependency(name: str, import_name: str, required: bool = True) -> bool:
    """Check if a Python package is importable."""
    try:
        __import__(import_name)
        console.print(f"  [green]{name}[/green] — installed")
        return True
    except ImportError:
        if required:
            console.print(f"  [red]{name}[/red] — MISSING (required)")
        else:
            console.print(f"  [yellow]{name}[/yellow] — not installed (optional)")
        return False


def _pull_ollama_model(model_name: str) -> None:
    """Pull a model via Ollama CLI."""
    console.print(f"\n  Pulling {model_name}...")
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            timeout=600,  # 10 minutes
        )
        if result.returncode == 0:
            console.print(f"  [green]Model '{model_name}' downloaded successfully[/green]")
        else:
            console.print(f"  [red]Failed to pull model (exit code {result.returncode})[/red]")
    except subprocess.TimeoutExpired:
        console.print("  [red]Model download timed out (10 min limit)[/red]")
    except FileNotFoundError:
        console.print("  [red]Ollama command not found[/red]")
