"""
DocForge — OCR Image Preprocessing
=====================================

Prepares rendered page images for OCR by applying:
  - Grayscale conversion
  - Deskew correction (straighten tilted scans)
  - Noise reduction (median filter)
  - Adaptive binarisation (Otsu's method)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

from docforge.infra.logging import get_logger

logger = get_logger(__name__)


def preprocess_for_ocr(image_path: str, output_path: str | None = None) -> str:
    """Preprocess an image for optimal OCR quality.

    Args:
        image_path:  Path to the input PNG image.
        output_path: Path for the preprocessed image. If None, overwrites input.

    Returns:
        Path to the preprocessed image.
    """
    output = output_path or image_path

    try:
        img = Image.open(image_path)

        # Step 1: Convert to grayscale
        img = ImageOps.grayscale(img)

        # Step 2: Noise reduction (median filter)
        img = img.filter(ImageFilter.MedianFilter(size=3))

        # Step 3: Increase contrast (auto-contrast)
        img = ImageOps.autocontrast(img, cutoff=1)

        # Step 4: Binarise (Otsu-like thresholding via point operation)
        threshold = _otsu_threshold(img)
        img = img.point(lambda p: 255 if p > threshold else 0, mode="1")

        # Convert back to grayscale for OCR compatibility
        img = img.convert("L")

        img.save(output)
        logger.debug("  Preprocessed for OCR: %s", Path(output).name)

    except Exception as exc:
        logger.warning("OCR preprocessing failed for %s: %s", image_path, exc)
        output = image_path  # Use original on failure

    return output


def _otsu_threshold(img: Image.Image) -> int:
    """Simple Otsu's thresholding for binarisation.

    Args:
        img: Grayscale PIL Image.

    Returns:
        Optimal threshold value (0–255).
    """
    histogram = img.histogram()
    total = sum(histogram)

    if total == 0:
        return 128

    sum_total = sum(i * histogram[i] for i in range(256))
    sum_bg = 0
    weight_bg = 0
    max_variance = 0
    threshold = 128

    for i in range(256):
        weight_bg += histogram[i]
        if weight_bg == 0:
            continue

        weight_fg = total - weight_bg
        if weight_fg == 0:
            break

        sum_bg += i * histogram[i]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg

        variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if variance > max_variance:
            max_variance = variance
            threshold = i

    return threshold
