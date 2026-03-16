"""
DocForge — CLI: model command
================================

Manage VLM models: list available, pull new ones, check status.
Currently supports Ollama as the primary model registry.
"""

from __future__ import annotations

import click

from docforge.infra.config import load_config
from docforge.infra.hardware import check_ollama_installed, profile_system
from docforge.infra.logging import setup_logging
from docforge.reporting.formatters import console, print_banner


# Recommended models with descriptions
RECOMMENDED_MODELS = {
    "minicpm-v":  "MiniCPM-V 2.6 — Best quality, needs 8+ GB RAM",
    "llava":      "LLaVA 7B — Good quality, needs 6+ GB RAM",
    "moondream":  "Moondream 2 — Lightweight, needs 4+ GB RAM",
}


def run_model(ctx: click.Context, action: str, model_name: str | None) -> None:
    """Execute the model subcommand."""
    config = load_config(ctx.obj.get("config_path"))
    if ctx.obj.get("verbose"):
        config.general.log_level = "DEBUG"
    setup_logging(config.general.log_level, config.general.log_path)

    print_banner()

    if action == "list":
        _list_models(config)
    elif action == "pull":
        _pull_model(config, model_name)
    elif action == "status":
        _model_status(config)


def _list_models(config) -> None:
    """List recommended and locally available models."""
    console.print("[bold]Recommended VLM Models:[/bold]\n")

    profile = profile_system()

    for name, desc in RECOMMENDED_MODELS.items():
        marker = "[green]recommended[/green]" if name == profile.recommended_vlm else ""
        console.print(f"  {name:15s}  {desc}  {marker}")

    console.print()

    # List locally available models (Ollama)
    if check_ollama_installed():
        console.print("[bold]Locally available (Ollama):[/bold]\n")
        try:
            from docforge.vlm.runtime_ollama import OllamaRuntime
            runtime = OllamaRuntime(model=config.vlm.model)
            models = runtime.list_models()
            if models:
                for m in models:
                    console.print(f"  {m}")
            else:
                console.print("  [dim]No models installed yet.[/dim]")
        except Exception as exc:
            console.print(f"  [red]Cannot query Ollama: {exc}[/red]")
    else:
        console.print("[dim]Ollama not installed. Install from https://ollama.ai[/dim]")

    console.print()


def _pull_model(config, model_name: str | None) -> None:
    """Pull (download) a model via Ollama."""
    if not check_ollama_installed():
        console.print(
            "[red]Ollama is not installed.[/red] "
            "Install from https://ollama.ai first."
        )
        return

    name = model_name or config.vlm.model
    console.print(f"[bold]Pulling model:[/bold] {name}\n")

    try:
        from docforge.vlm.runtime_ollama import OllamaRuntime
        runtime = OllamaRuntime(model=name)
        runtime.pull_model()
        console.print(f"\n[green]Model '{name}' is ready.[/green]\n")
    except Exception as exc:
        console.print(f"\n[red]Failed to pull model: {exc}[/red]\n")


def _model_status(config) -> None:
    """Check the status of the configured VLM model."""
    console.print(f"[bold]VLM Configuration:[/bold]")
    console.print(f"  Model:   {config.vlm.model}")
    console.print(f"  Runtime: {config.vlm.runtime}")
    console.print(f"  Enabled: {config.vlm.enabled}")
    console.print()

    profile = profile_system()
    console.print(f"[bold]System Capabilities:[/bold]")
    console.print(f"  Available RAM:    {profile.available_ram_gb:.1f} GB")
    console.print(f"  Can run VLM:      {'Yes' if profile.can_run_vlm else 'No'}")
    console.print(f"  Recommended VLM:  {profile.recommended_vlm or 'N/A'}")
    console.print(f"  GPU:              {profile.gpu_name or 'Not detected'}")
    console.print()

    if check_ollama_installed():
        console.print("[green]Ollama:[/green] installed")
    else:
        console.print("[yellow]Ollama:[/yellow] not installed")

    console.print()
