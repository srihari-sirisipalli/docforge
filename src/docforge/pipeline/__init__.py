"""
DocForge — Pipeline Package
==============================

Core processing pipeline with two-track parallel execution:
  - Fast path: Text heuristic extraction for clean digital PDFs
  - VLM path: Vision-Language Model for scanned/image PDFs

The orchestrator coordinates scanning, routing, extraction, merging,
naming, and reporting stages.
"""

from docforge.pipeline.orchestrator import PipelineOrchestrator

__all__ = ["PipelineOrchestrator"]
