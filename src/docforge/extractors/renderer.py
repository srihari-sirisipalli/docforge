"""
DocForge — Stage 2: Page Renderer
====================================

Renders PDF pages to PNG images using PyMuPDF for consumption by the
VLM (primary) or OCR (fallback) engines.

Shared by both paths — the only difference is the target DPI:
  - VLM: 200 DPI (balance quality vs. speed)
  - OCR: 300 DPI (OCR needs higher resolution)

Rendered images are stored in a temporary directory and cleaned up
after each document is processed.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from docforge.infra.config import RuntimeConfig
from docforge.infra.logging import get_logger

logger = get_logger(__name__)


class PageRenderer:
    """Renders PDF pages to PNG images for VLM or OCR processing.

    Images are saved to a temp directory with filenames based on file_id,
    making cleanup straightforward.
    """

    def __init__(self, config: RuntimeConfig):
        self.vlm_dpi = config.vlm.render_dpi       # Default: 200
        self.ocr_dpi = config.ocr.dpi               # Default: 300
        self.max_pages = config.extraction.max_pages_render  # Default: 2
        self.temp_dir = Path(config.general.temp_dir) / "renders"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        pdf_path: str,
        file_id: str,
        purpose: str = "vlm",
    ) -> list[str]:
        """Render the first N pages of a PDF to PNG images.

        Uses smart DPI selection based on text density of each page:
          - Rich text (>100 words): lower DPI (faster)
          - Moderate text: standard DPI
          - Very little text (scanned/diagram): higher DPI + include page 2

        Args:
            pdf_path: Path to the PDF file.
            file_id:  Document identifier (used for temp filenames).
            purpose:  "vlm" or "ocr" — determines base DPI.

        Returns:
            List of paths to the rendered PNG files.
        """
        base_dpi = self.vlm_dpi if purpose == "vlm" else self.ocr_dpi
        output_paths: list[str] = []

        logger.debug("  Rendering pages: %s (purpose=%s, dpi=%d)", file_id[:12], purpose, base_dpi)

        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            logger.error("Cannot open PDF for rendering: %s — %s", pdf_path, exc)
            return []

        try:
            pages_to_render = min(self.max_pages, len(doc))

            # Smart DPI: check page 1 text density
            if len(doc) > 0:
                page1_text = doc[0].get_text("text")
                word_count = len(page1_text.split())

                if word_count > 100:
                    # Rich text — can use lower DPI
                    render_dpi = max(150, base_dpi - 50)
                    pages_to_render = min(pages_to_render, 1)
                elif word_count > 20:
                    # Moderate text — standard DPI
                    render_dpi = base_dpi
                    pages_to_render = min(pages_to_render, 1)
                else:
                    # Very little text (scanned/diagram) — higher DPI, more pages
                    render_dpi = min(300, base_dpi + 50)
                    pages_to_render = min(self.max_pages, len(doc))
            else:
                render_dpi = base_dpi

            # Render each page
            for page_num in range(pages_to_render):
                page = doc[page_num]

                # Convert DPI to zoom factor (72 is default PDF DPI)
                zoom = render_dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # Save to temp directory
                output_path = str(self.temp_dir / f"{file_id}_p{page_num}.png")
                pix.save(output_path)
                output_paths.append(output_path)

                logger.debug(
                    "  Rendered page %d: %dx%d px @ %d DPI → %s",
                    page_num, pix.width, pix.height, render_dpi,
                    Path(output_path).name,
                )

        finally:
            doc.close()

        return output_paths

    def cleanup(self, file_id: str) -> int:
        """Remove temporary rendered images for a specific document.

        Args:
            file_id: Document identifier.

        Returns:
            Number of files removed.
        """
        removed = 0
        for f in self.temp_dir.glob(f"{file_id}_*.png"):
            f.unlink(missing_ok=True)
            removed += 1
        return removed

    def cleanup_all(self) -> int:
        """Remove ALL temporary rendered images.

        Called at the end of a processing run.

        Returns:
            Number of files removed.
        """
        removed = 0
        for f in self.temp_dir.glob("*.png"):
            f.unlink(missing_ok=True)
            removed += 1

        if removed:
            logger.info("Cleaned up %d temporary render files", removed)
        return removed
