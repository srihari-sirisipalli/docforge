"""
DocForge — Infrastructure Package
===================================

System-level utilities: logging, configuration, hardware profiling,
memory management, and external drive support.
"""

from docforge.infra.config import RuntimeConfig, load_config, save_config
from docforge.infra.drives import DriveManager, DriveType
from docforge.infra.hardware import SystemProfile, profile_system
from docforge.infra.logging import get_logger, setup_logging
from docforge.infra.memory import MemoryGuard

__all__ = [
    "setup_logging", "get_logger",
    "RuntimeConfig", "load_config", "save_config",
    "SystemProfile", "profile_system",
    "MemoryGuard",
    "DriveManager", "DriveType",
]
