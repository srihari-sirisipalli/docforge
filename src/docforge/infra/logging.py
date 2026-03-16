"""
DocForge — Structured Logging
==============================

Sets up a dual-output logging system:
  1. Console output via Rich for beautiful, colour-coded terminal messages
  2. Rotating file output for persistent debug logs

Usage:
    from docforge.infra.logging import setup_logging, get_logger
    setup_logging(level="INFO")
    logger = get_logger(__name__)
    logger.info("Processing started", extra={"docs": 1500})
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


# Module-level default — overridden by setup_logging()
_LOG_DIR: Path = Path.home() / ".docforge" / "logs"
_INITIALISED: bool = False


def setup_logging(
    level: str = "INFO",
    log_dir: str | Path | None = None,
    console: bool = True,
) -> None:
    """Initialise the DocForge logging system.

    Call this once at application startup (typically from the CLI entry point).

    Args:
        level:    Logging level name — DEBUG, INFO, WARNING, ERROR, CRITICAL.
        log_dir:  Directory for log files. Defaults to ~/.docforge/logs/.
        console:  Whether to enable Rich console output (disable in tests).
    """
    global _LOG_DIR, _INITIALISED

    if _INITIALISED:
        return  # Prevent double-init in tests or re-entrant calls

    _LOG_DIR = Path(log_dir) if log_dir else _LOG_DIR
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, level.upper(), logging.INFO)

    # ── Root logger configuration ───────────────────────────────────────
    root = logging.getLogger("docforge")
    root.setLevel(log_level)
    root.handlers.clear()

    # ── Console handler (Rich) ──────────────────────────────────────────
    if console:
        console_handler = RichHandler(
            level=log_level,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(console_handler)

    # ── File handler (rotating, detailed) ───────────────────────────────
    log_file = _LOG_DIR / "docforge.log"
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=10 * 1024 * 1024,   # 10 MB per file
        backupCount=5,               # Keep 5 rotated files
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(file_handler)

    _INITIALISED = True
    root.debug("Logging initialised — level=%s, log_dir=%s", level, _LOG_DIR)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the 'docforge' namespace.

    Args:
        name: Typically ``__name__`` from the calling module.

    Returns:
        A logging.Logger instance, e.g., ``docforge.extractors.vlm``.
    """
    # Ensure the logger is under the docforge namespace
    if not name.startswith("docforge"):
        name = f"docforge.{name}"
    return logging.getLogger(name)
