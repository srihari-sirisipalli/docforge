"""
DocForge — VLM Subsystem
==========================

Vision-Language Model integration for document metadata extraction.
Supports Ollama (recommended), llama.cpp, and HuggingFace Transformers.
"""

from docforge.vlm.manager import ModelManager
from docforge.vlm.parser import parse_vlm_response
from docforge.vlm.prompts import VLM_EXTRACTION_PROMPT, build_vlm_prompt

__all__ = [
    "ModelManager", "parse_vlm_response",
    "VLM_EXTRACTION_PROMPT", "build_vlm_prompt",
]
