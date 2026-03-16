"""
DocForge — Configuration Management
=====================================

TOML-based configuration with sensible defaults, schema validation,
and hardware-aware auto-tuning.

Configuration hierarchy (highest priority first):
  1. CLI arguments (--vlm, --max-workers, etc.)
  2. Per-directory .docforge.toml (if present in source directory)
  3. User config at ~/.docforge/config.toml
  4. Built-in defaults (defined in this module)

Usage:
    from docforge.infra.config import load_config, RuntimeConfig
    config = load_config()                    # Load from default location
    config = load_config("/path/to/custom.toml")  # Load from custom path
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from docforge.infra.logging import get_logger

logger = get_logger(__name__)

# TOML parser — use stdlib tomllib on 3.11+, fall back to tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]


# =============================================================================
# Configuration Section Dataclasses
# =============================================================================

@dataclass
class GeneralConfig:
    """General application settings."""
    db_path: str = "~/.docforge/state.db"
    log_path: str = "~/.docforge/logs/"
    log_level: str = "INFO"
    temp_dir: str = "~/.docforge/tmp"

    def resolve_paths(self) -> None:
        """Expand ~ and environment variables in all path fields."""
        self.db_path = str(Path(self.db_path).expanduser())
        self.log_path = str(Path(self.log_path).expanduser())
        self.temp_dir = str(Path(self.temp_dir).expanduser())


@dataclass
class ScannerConfig:
    """File discovery and scanning settings."""
    recursive: bool = True
    follow_symlinks: bool = False
    skip_hidden: bool = True
    min_file_size: int = 1024           # Skip files under 1 KB
    max_file_size: int = 2_147_483_648  # Skip files over 2 GB
    file_patterns: list[str] = field(default_factory=lambda: ["*.pdf"])


@dataclass
class ExtractionConfig:
    """Controls for the extraction pipeline."""
    max_pages_render: int = 2     # Render first N pages for VLM/OCR
    max_pages_text: int = 5       # Extract embedded text from first N pages
    text_quality_threshold: float = 0.3  # Below this, text is unusable


@dataclass
class VLMConfig:
    """Vision-Language Model configuration."""
    enabled: bool = True
    runtime: str = "ollama"       # "ollama" | "llamacpp" | "transformers"
    model: str = "minicpm-v"      # "minicpm-v" | "llava" | "moondream"
    model_path: str = "~/.docforge/models/"
    mmproj_path: str = ""         # Multimodal projection file for llama.cpp
    hf_model_id: str = ""         # HuggingFace model ID for Transformers
    context_length: int = 4096
    max_tokens: int = 1024
    temperature: float = 0.1      # Low for deterministic extraction
    threads: int = 4
    gpu_layers: int = 0           # 0 = CPU only
    render_dpi: int = 200
    timeout_seconds: int = 120
    ollama_port: int = 11434
    llamacpp_port: int = 8080
    fallback_model: str = "llava"         # Lighter model to try if primary fails


@dataclass
class OCRConfig:
    """OCR fallback settings (only used when VLM is unavailable)."""
    enabled: bool = True
    engine: str = "tesseract"     # "tesseract" | "easyocr"
    languages: list[str] = field(default_factory=lambda: ["eng"])
    dpi: int = 300
    preprocess: bool = True       # Enable deskew + denoise
    max_concurrent: int = 2


@dataclass
class NamingConfig:
    """Filename generation settings."""
    default_template: str = "{type}_{org}_{title_short}_{year}"
    max_length: int = 80
    collision_strategy: str = "suffix"  # "suffix" | "hash"
    lowercase: bool = True
    separator: str = "_"
    strip_accents: bool = True


@dataclass
class OrganizerConfig:
    """Folder organisation settings."""
    enabled: bool = True
    strategy: str = "type"
    # Options: "year", "type", "year_type", "domain_type", "domain_year"
    base_dir: str = "./organized/"


@dataclass
class PerformanceConfig:
    """Resource management and parallelism settings."""
    max_workers: int = 0           # 0 = auto-detect
    batch_size: int = 100
    memory_limit_mb: int = 0       # 0 = auto (70% of available)
    io_priority: str = "normal"
    vlm_concurrent: int = 1        # VLM: typically 1 (uses all threads)
    fast_path_workers: int = 0     # 0 = auto (max_workers - vlm_concurrent)


@dataclass
class SafetyConfig:
    """Safety and reversibility settings."""
    dry_run: bool = True           # Default: preview only, don't rename
    backup_originals: bool = False
    require_confirmation: bool = True


@dataclass
class ExportConfig:
    """Export and reporting settings."""
    excel_columns: list[str] = field(default_factory=lambda: [
        "original_file", "original_location", "renamed_file",
        "moved_to_location", "document_type", "organization",
        "author", "date", "confidence", "extraction_method", "status",
    ])


# =============================================================================
# RuntimeConfig — Top-level configuration object
# =============================================================================

@dataclass
class RuntimeConfig:
    """Complete runtime configuration assembled from TOML + CLI overrides.

    This is the single configuration object that all modules consume.
    """
    general: GeneralConfig = field(default_factory=GeneralConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    vlm: VLMConfig = field(default_factory=VLMConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    naming: NamingConfig = field(default_factory=NamingConfig)
    organizer: OrganizerConfig = field(default_factory=OrganizerConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    def resolve_all_paths(self) -> None:
        """Expand ~ in all path-containing config fields."""
        self.general.resolve_paths()
        self.vlm.model_path = str(Path(self.vlm.model_path).expanduser())
        self.organizer.base_dir = str(Path(self.organizer.base_dir).expanduser())


# =============================================================================
# Config Loading & Saving
# =============================================================================

DEFAULT_CONFIG_PATH = Path.home() / ".docforge" / "config.toml"


def load_config(path: str | Path | None = None) -> RuntimeConfig:
    """Load configuration from a TOML file, falling back to built-in defaults.

    Args:
        path: Path to the TOML config file. If None, uses ~/.docforge/config.toml.
              If the file doesn't exist, returns default configuration.

    Returns:
        A fully resolved RuntimeConfig instance.
    """
    config = RuntimeConfig()
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    if config_path.exists():
        if tomllib is None:
            logger.warning(
                "TOML parser not available (install 'tomli' for Python <3.11). "
                "Using default configuration."
            )
        else:
            logger.info("Loading configuration from %s", config_path)
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            config = _apply_toml(config, data)
    else:
        logger.info(
            "Config file not found at %s — using defaults. "
            "Run 'docforge setup' to generate one.",
            config_path,
        )

    config.resolve_all_paths()
    return config


def _apply_toml(config: RuntimeConfig, data: dict) -> RuntimeConfig:
    """Apply TOML data dictionary onto a RuntimeConfig, field by field.

    Unknown keys are silently ignored (forward compatibility).
    """
    section_map = {
        "general": config.general,
        "scanner": config.scanner,
        "extraction": config.extraction,
        "vlm": config.vlm,
        "ocr": config.ocr,
        "naming": config.naming,
        "organizer": config.organizer,
        "performance": config.performance,
        "safety": config.safety,
        "export": config.export,
    }
    for section_name, section_obj in section_map.items():
        if section_name in data:
            for key, value in data[section_name].items():
                if hasattr(section_obj, key):
                    setattr(section_obj, key, value)
                else:
                    logger.debug("Ignoring unknown config key: [%s].%s", section_name, key)
    return config


def save_config(config: RuntimeConfig, path: str | Path | None = None) -> Path:
    """Save the current configuration as a TOML file.

    Args:
        config: The RuntimeConfig to save.
        path:   Output path. Defaults to ~/.docforge/config.toml.

    Returns:
        The path where the config was written.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# =============================================================================",
        "# DocForge Configuration",
        "# =============================================================================",
        "# Generated automatically. Edit as needed.",
        "# Documentation: https://github.com/your-repo/docforge",
        "",
        "[general]",
        f'db_path = "{config.general.db_path}"',
        f'log_path = "{config.general.log_path}"',
        f'log_level = "{config.general.log_level}"',
        f'temp_dir = "{config.general.temp_dir}"',
        "",
        "[scanner]",
        f"recursive = {str(config.scanner.recursive).lower()}",
        f"follow_symlinks = {str(config.scanner.follow_symlinks).lower()}",
        f"skip_hidden = {str(config.scanner.skip_hidden).lower()}",
        f"min_file_size = {config.scanner.min_file_size}",
        f"max_file_size = {config.scanner.max_file_size}",
        "",
        "[extraction]",
        f"max_pages_render = {config.extraction.max_pages_render}",
        f"max_pages_text = {config.extraction.max_pages_text}",
        f"text_quality_threshold = {config.extraction.text_quality_threshold}",
        "",
        "# --- Vision-Language Model (PRIMARY extraction engine) ---",
        "[vlm]",
        f"enabled = {str(config.vlm.enabled).lower()}",
        f'runtime = "{config.vlm.runtime}"',
        f'model = "{config.vlm.model}"',
        f'model_path = "{config.vlm.model_path}"',
        f"context_length = {config.vlm.context_length}",
        f"max_tokens = {config.vlm.max_tokens}",
        f"temperature = {config.vlm.temperature}",
        f"threads = {config.vlm.threads}",
        f"gpu_layers = {config.vlm.gpu_layers}",
        f"render_dpi = {config.vlm.render_dpi}",
        f"timeout_seconds = {config.vlm.timeout_seconds}",
        f'fallback_model = "{config.vlm.fallback_model}"',
        "",
        "# --- OCR Fallback (only used if VLM is disabled) ---",
        "[ocr]",
        f"enabled = {str(config.ocr.enabled).lower()}",
        f'engine = "{config.ocr.engine}"',
        f"dpi = {config.ocr.dpi}",
        f"preprocess = {str(config.ocr.preprocess).lower()}",
        "",
        "[naming]",
        f'default_template = "{config.naming.default_template}"',
        f"max_length = {config.naming.max_length}",
        f'collision_strategy = "{config.naming.collision_strategy}"',
        f"lowercase = {str(config.naming.lowercase).lower()}",
        f'separator = "{config.naming.separator}"',
        f"strip_accents = {str(config.naming.strip_accents).lower()}",
        "",
        "[organizer]",
        f"enabled = {str(config.organizer.enabled).lower()}",
        f'strategy = "{config.organizer.strategy}"',
        f'base_dir = "{config.organizer.base_dir}"',
        "",
        "[performance]",
        f"max_workers = {config.performance.max_workers}",
        f"batch_size = {config.performance.batch_size}",
        f"memory_limit_mb = {config.performance.memory_limit_mb}",
        f"vlm_concurrent = {config.performance.vlm_concurrent}",
        f"fast_path_workers = {config.performance.fast_path_workers}",
        "",
        "[safety]",
        f"dry_run = {str(config.safety.dry_run).lower()}",
        f"backup_originals = {str(config.safety.backup_originals).lower()}",
        f"require_confirmation = {str(config.safety.require_confirmation).lower()}",
        "",
    ]

    config_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Configuration saved to %s", config_path)
    return config_path
