"""
DocForge — OCR Engine (Fallback Path C)
=========================================

OCR fallback for systems that cannot run a VLM. Runs Tesseract on
rendered page images and passes the result to the heuristic extractor.

This is the lowest-quality extraction path but works on any system
with Tesseract installed (~200 MB RAM).
"""

from __future__ import annotations

import time

from docforge.infra.logging import get_logger
from docforge.ocr.postprocess import postprocess_ocr_text
from docforge.ocr.preprocess import preprocess_for_ocr

logger = get_logger(__name__)


class OCREngine:
    """OCR fallback engine using Tesseract.

    Preprocesses images, runs Tesseract, post-processes the text,
    and stores results on the DocumentRecord.
    """

    def __init__(self, languages: list[str] | None = None, preprocess: bool = True):
        """
        Args:
            languages:  List of Tesseract language codes (default: ["eng"]).
            preprocess: Whether to apply image preprocessing.
        """
        self.languages = languages or ["eng"]
        self.preprocess = preprocess
        self._tesseract_available: bool | None = None

    def is_available(self) -> bool:
        """Check if Tesseract is installed and accessible."""
        if self._tesseract_available is not None:
            return self._tesseract_available

        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._tesseract_available = True
        except Exception:
            self._tesseract_available = False

        return self._tesseract_available

    def process(self, page_images: list[str], record) -> None:
        """Run OCR on rendered page images and store results.

        Args:
            page_images: List of paths to rendered PNG images.
            record:      DocumentRecord to populate with OCR text.
        """
        if not self.is_available():
            logger.warning(
                "Tesseract not available — skipping OCR for %s",
                record.file_id[:12],
            )
            return

        import pytesseract
        from PIL import Image

        start = time.perf_counter()
        logger.debug("Stage 3 (OCR) — Processing: %s", record.file_id[:12])

        all_text: list[str] = []
        total_confidence = 0.0
        page_count = 0

        for img_path in page_images:
            try:
                # Preprocess if enabled
                processed_path = img_path
                if self.preprocess:
                    processed_path = preprocess_for_ocr(img_path)

                # Run Tesseract
                lang_str = "+".join(self.languages)
                img = Image.open(processed_path)
                text = pytesseract.image_to_string(img, lang=lang_str)

                # Get confidence data
                data = pytesseract.image_to_data(
                    img, lang=lang_str, output_type=pytesseract.Output.DICT,
                )
                confidences = [
                    int(c) for c in data.get("conf", [])
                    if str(c).isdigit() and int(c) > 0
                ]
                avg_conf = sum(confidences) / max(len(confidences), 1)

                # Post-process
                text = postprocess_ocr_text(text)
                all_text.append(text)
                total_confidence += avg_conf
                page_count += 1

            except Exception as exc:
                logger.warning("OCR failed for page %s: %s", img_path, exc)

        # Store results
        record.ocr_text = "\n".join(all_text)
        record.ocr_confidence = (total_confidence / max(page_count, 1)) / 100.0

        # If we got OCR text but no raw_text, use OCR text as raw_text
        if record.ocr_text and not record.raw_text:
            record.raw_text = record.ocr_text

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.debug(
            "  OCR results: %d chars, confidence=%.2f — %d ms",
            len(record.ocr_text), record.ocr_confidence, elapsed_ms,
        )
