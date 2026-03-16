"""
DocForge — Strategy Router
=============================

Determines the extraction strategy for each document based on:
  1. Text quality score (from Stage 2)
  2. VLM availability
  3. OCR availability
  4. Configuration overrides

Strategy Decision Tree:
  ┌── text_quality >= 0.7 ──→ TEXT_HEURISTIC (fast path)
  │
  ├── text_quality >= 0.3 ──→ VLM_PLUS_HEURISTIC (cross-validate)
  │   └── VLM unavailable ──→ TEXT_HEURISTIC (degraded)
  │
  ├── text_quality < 0.3 ───→ VLM_ONLY (scanned/image PDF)
  │   └── VLM unavailable ──→ OCR_HEURISTIC (fallback)
  │       └── OCR unavailable → METADATA_ONLY (last resort)
  │
  └── VLM forced off ──────→ TEXT_HEURISTIC or OCR_HEURISTIC
"""

from __future__ import annotations

from docforge.infra.logging import get_logger
from docforge.models.enums import ExtractionStrategy
from docforge.models.record import DocumentRecord

logger = get_logger(__name__)

# Quality thresholds for routing decisions
HIGH_QUALITY_THRESHOLD = 0.7   # Good embedded text — heuristic is sufficient
MEDIUM_QUALITY_THRESHOLD = 0.3  # Partial text — VLM + heuristic cross-validation


class StrategyRouter:
    """Routes documents to the appropriate extraction strategy.

    The router makes a single decision per document based on text quality
    and system capabilities. This decision cannot be changed mid-pipeline
    (determinism guarantee).
    """

    def __init__(
        self,
        vlm_available: bool = False,
        ocr_available: bool = False,
        vlm_enabled: bool = True,
    ):
        """
        Args:
            vlm_available: Whether a VLM runtime is currently running.
            ocr_available: Whether Tesseract OCR is installed.
            vlm_enabled:   Whether VLM is enabled in configuration.
        """
        self.vlm_available = vlm_available and vlm_enabled
        self.ocr_available = ocr_available

        logger.info(
            "Strategy router: VLM=%s, OCR=%s",
            "available" if self.vlm_available else "unavailable",
            "available" if self.ocr_available else "unavailable",
        )

    def route(self, record: DocumentRecord) -> ExtractionStrategy:
        """Determine the extraction strategy for a document.

        Reads record.text_quality_score (set by Stage 2) and system
        capabilities to select the optimal path.

        Args:
            record: DocumentRecord with text_quality_score populated.

        Returns:
            The selected ExtractionStrategy.
        """
        quality = record.text_quality_score

        # High-quality embedded text — fast path is sufficient
        if quality >= HIGH_QUALITY_THRESHOLD:
            strategy = ExtractionStrategy.TEXT_HEURISTIC
            logger.debug(
                "  Route %s → TEXT_HEURISTIC (quality=%.2f, above %.1f)",
                record.file_id[:12], quality, HIGH_QUALITY_THRESHOLD,
            )

        # Medium quality — cross-validate VLM + heuristic
        elif quality >= MEDIUM_QUALITY_THRESHOLD:
            if self.vlm_available:
                strategy = ExtractionStrategy.VLM_PLUS_HEURISTIC
                logger.debug(
                    "  Route %s → VLM_PLUS_HEURISTIC (quality=%.2f)",
                    record.file_id[:12], quality,
                )
            else:
                strategy = ExtractionStrategy.TEXT_HEURISTIC
                logger.debug(
                    "  Route %s → TEXT_HEURISTIC (VLM unavailable, quality=%.2f)",
                    record.file_id[:12], quality,
                )

        # Low quality — scanned/image PDF, needs VLM
        else:
            if self.vlm_available:
                strategy = ExtractionStrategy.VLM_ONLY
                logger.debug(
                    "  Route %s → VLM_ONLY (quality=%.2f, below %.1f)",
                    record.file_id[:12], quality, MEDIUM_QUALITY_THRESHOLD,
                )
            elif self.ocr_available:
                strategy = ExtractionStrategy.OCR_HEURISTIC
                logger.debug(
                    "  Route %s → OCR_HEURISTIC (VLM unavailable, quality=%.2f)",
                    record.file_id[:12], quality,
                )
            else:
                strategy = ExtractionStrategy.METADATA_ONLY
                logger.debug(
                    "  Route %s → METADATA_ONLY (no VLM/OCR, quality=%.2f)",
                    record.file_id[:12], quality,
                )

        record.extraction_strategy = strategy.value
        return strategy
