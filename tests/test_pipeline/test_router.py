"""Tests for the strategy router."""

from docforge.models.enums import ExtractionStrategy
from docforge.models.record import DocumentRecord
from docforge.pipeline.router import StrategyRouter


class TestStrategyRouter:
    """Test extraction strategy routing decisions."""

    def test_high_quality_routes_to_heuristic(self):
        router = StrategyRouter(vlm_available=True, ocr_available=True)
        record = DocumentRecord(text_quality_score=0.85)

        strategy = router.route(record)
        assert strategy == ExtractionStrategy.TEXT_HEURISTIC

    def test_medium_quality_with_vlm(self):
        router = StrategyRouter(vlm_available=True, ocr_available=True)
        record = DocumentRecord(text_quality_score=0.5)

        strategy = router.route(record)
        assert strategy == ExtractionStrategy.VLM_PLUS_HEURISTIC

    def test_medium_quality_without_vlm(self):
        router = StrategyRouter(vlm_available=False, ocr_available=True)
        record = DocumentRecord(text_quality_score=0.5)

        strategy = router.route(record)
        assert strategy == ExtractionStrategy.TEXT_HEURISTIC

    def test_low_quality_with_vlm(self):
        router = StrategyRouter(vlm_available=True, ocr_available=True)
        record = DocumentRecord(text_quality_score=0.1)

        strategy = router.route(record)
        assert strategy == ExtractionStrategy.VLM_ONLY

    def test_low_quality_ocr_fallback(self):
        router = StrategyRouter(vlm_available=False, ocr_available=True)
        record = DocumentRecord(text_quality_score=0.1)

        strategy = router.route(record)
        assert strategy == ExtractionStrategy.OCR_HEURISTIC

    def test_no_vlm_no_ocr(self):
        router = StrategyRouter(vlm_available=False, ocr_available=False)
        record = DocumentRecord(text_quality_score=0.1)

        strategy = router.route(record)
        assert strategy == ExtractionStrategy.METADATA_ONLY

    def test_strategy_stored_on_record(self):
        router = StrategyRouter(vlm_available=False, ocr_available=False)
        record = DocumentRecord(text_quality_score=0.9)

        router.route(record)
        assert record.extraction_strategy == "text_heuristic"
