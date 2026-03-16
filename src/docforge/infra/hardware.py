"""
DocForge — Hardware Profiling
==============================

Detects system capabilities at startup to auto-configure:
  - Number of worker threads
  - VLM model selection and quantisation level
  - Memory budget for processing
  - Disk type (SSD vs HDD) for I/O scheduling

Usage:
    from docforge.infra.hardware import profile_system
    profile = profile_system()
    print(f"RAM: {profile.available_ram_gb:.1f} GB, VLM: {profile.recommended_vlm}")
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass

import psutil

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SystemProfile:
    """Hardware profile used for auto-configuration decisions.

    The pipeline reads this at startup to select VLM models, thread counts,
    batch sizes, and memory budgets.
    """
    cpu_cores: int = 2
    cpu_name: str = "Unknown"
    total_ram_gb: float = 4.0
    available_ram_gb: float = 2.0
    disk_type: str = "unknown"       # "ssd" | "hdd" | "network" | "unknown"
    gpu_available: bool = False
    gpu_name: str = ""
    gpu_vram_gb: float = 0.0
    can_run_vlm: bool = False
    recommended_vlm: str = ""
    recommended_workers: int = 1
    recommended_vlm_threads: int = 2
    os_name: str = ""
    python_version: str = ""


def profile_system(target_path: str | None = None) -> SystemProfile:
    """Profile the current system hardware and return recommendations.

    Args:
        target_path: Optional path to check disk type for (SSD vs HDD).

    Returns:
        A SystemProfile with auto-tuned recommendations.
    """
    logger.info("Profiling system hardware...")

    profile = SystemProfile()

    # ── CPU ──────────────────────────────────────────────────────────────
    profile.cpu_cores = os.cpu_count() or 2
    profile.cpu_name = platform.processor() or "Unknown"
    profile.os_name = f"{platform.system()} {platform.release()}"
    profile.python_version = platform.python_version()

    # ── Memory ───────────────────────────────────────────────────────────
    mem = psutil.virtual_memory()
    profile.total_ram_gb = mem.total / (1024 ** 3)
    profile.available_ram_gb = mem.available / (1024 ** 3)

    # ── Disk ─────────────────────────────────────────────────────────────
    if target_path:
        profile.disk_type = _detect_disk_type(target_path)

    # ── GPU ──────────────────────────────────────────────────────────────
    profile.gpu_available, profile.gpu_name, profile.gpu_vram_gb = _check_gpu()

    # ── VLM Recommendations ─────────────────────────────────────────────
    avail = profile.available_ram_gb

    if avail >= 10:
        profile.can_run_vlm = True
        profile.recommended_vlm = "minicpm-v"
    elif avail >= 6:
        profile.can_run_vlm = True
        profile.recommended_vlm = "minicpm-v"
    elif avail >= 4:
        profile.can_run_vlm = True
        profile.recommended_vlm = "llava"
    else:
        profile.can_run_vlm = False
        profile.recommended_vlm = ""

    # If GPU is available with enough VRAM, prefer larger model
    if profile.gpu_available and profile.gpu_vram_gb >= 6:
        profile.recommended_vlm = "minicpm-v"
        profile.can_run_vlm = True

    # ── Worker Recommendations ───────────────────────────────────────────
    profile.recommended_workers = max(1, profile.cpu_cores - 1)
    profile.recommended_vlm_threads = max(1, profile.cpu_cores // 2)

    logger.info(
        "System profile: %d cores, %.1f GB RAM (%.1f available), "
        "GPU=%s, VLM=%s",
        profile.cpu_cores,
        profile.total_ram_gb,
        profile.available_ram_gb,
        profile.gpu_name or "none",
        profile.recommended_vlm or "none (insufficient RAM)",
    )

    return profile


def _detect_disk_type(path: str) -> str:
    """Attempt to detect whether the target path is on SSD or HDD.

    Returns 'ssd', 'hdd', 'network', or 'unknown'.
    """
    try:
        # Check for network paths
        if path.startswith("\\\\") or path.startswith("//"):
            return "network"

        # On Windows, use PowerShell to query disk type
        if platform.system() == "Windows":
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PhysicalDisk | Select-Object MediaType | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10,
            )
            if "SSD" in result.stdout or "Solid State" in result.stdout:
                return "ssd"
            elif "HDD" in result.stdout or "Unspecified" in result.stdout:
                return "hdd"

        # On Linux, check rotational flag
        elif platform.system() == "Linux":
            # Find the block device for this path
            result = subprocess.run(
                ["lsblk", "-no", "ROTA", "-d"],
                capture_output=True, text=True, timeout=10,
            )
            if "0" in result.stdout:
                return "ssd"
            elif "1" in result.stdout:
                return "hdd"

    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    return "unknown"


def _check_gpu() -> tuple[bool, str, float]:
    """Check for GPU availability and VRAM.

    Returns:
        Tuple of (is_available, gpu_name, vram_gb).
    """
    # Try NVIDIA GPU via nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            name = parts[0].strip()
            vram_mb = float(parts[1].strip())
            return True, name, vram_mb / 1024
    except (subprocess.SubprocessError, FileNotFoundError, ValueError, IndexError):
        pass

    return False, "", 0.0


def check_ollama_installed() -> bool:
    """Check if Ollama is installed and accessible."""
    return shutil.which("ollama") is not None


def check_tesseract_installed() -> bool:
    """Check if Tesseract OCR is installed and accessible."""
    if shutil.which("tesseract") is not None:
        return True
    # Check standard Windows install paths
    if platform.system() == "Windows":
        for prog_dir in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
            if prog_dir:
                candidate = os.path.join(prog_dir, "Tesseract-OCR", "tesseract.exe")
                if os.path.isfile(candidate):
                    return True
    return False


def get_tesseract_path() -> str | None:
    """Return the full path to the Tesseract executable, or None."""
    path = shutil.which("tesseract")
    if path:
        return path
    if platform.system() == "Windows":
        for prog_dir in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
            if prog_dir:
                candidate = os.path.join(prog_dir, "Tesseract-OCR", "tesseract.exe")
                if os.path.isfile(candidate):
                    return candidate
    return None
