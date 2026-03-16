"""
DocForge — Module Entry Point
================================

Enables running DocForge as a Python module:
    python -m docforge [command] [options]

Equivalent to the 'docforge' CLI entry point.
"""

from docforge.cli.main import cli

if __name__ == "__main__":
    cli()
