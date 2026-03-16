"""Tests for the StateDB — document CRUD, work distribution, and job management."""

from docforge.models.record import PendingDocument
from docforge.storage.database import StateDB


class TestInsertAndQuery:
    """Test document insertion and basic queries."""

    def test_insert_pending_documents(self, db, sample_pending):
        count = db.insert_pending_documents(sample_pending)
        assert db.get_total_count() == 5

    def test_duplicate_insert_skipped(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        db.insert_pending_documents(sample_pending)  # Same file_ids
        assert db.get_total_count() == 5

    def test_get_all_pending(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        pending = db.get_all_pending()
        assert len(pending) == 5
        assert all(isinstance(p, tuple) and len(p) == 2 for p in pending)

    def test_get_total_count_empty(self, db):
        assert db.get_total_count() == 0

    def test_get_record_not_found(self, db):
        assert db.get_record("nonexistent") is None


class TestWorkDistribution:
    """Test claim-based work distribution for parallel processing."""

    def test_claim_fast_path(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        # Set text quality high for one doc so it qualifies for fast path
        db.update_text_probe("hash_0000", "Some good text here", 0.8)

        claimed = db.claim_next_fast_path(worker_id=0)
        assert claimed is not None
        assert claimed["file_id"] == "hash_0000"

    def test_claim_fast_path_empty(self, db):
        assert db.claim_next_fast_path(worker_id=0) is None

    def test_claim_vlm_needed(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        # Low quality text → needs VLM
        db.update_text_probe("hash_0001", "", 0.1)

        claimed = db.claim_next_vlm_needed()
        assert claimed is not None
        # Any doc with quality < 0.3 qualifies; ordered by file_size ASC
        assert claimed["file_id"] in [p.file_id for p in sample_pending]

    def test_claimed_doc_not_reclaimed(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        db.update_text_probe("hash_0000", "text", 0.8)

        first = db.claim_next_fast_path(0)
        second = db.claim_next_fast_path(1)
        # Second claim should get a different doc or None
        if second is not None:
            assert second["file_id"] != first["file_id"]


class TestErrorHandling:
    """Test error marking and fallback queueing."""

    def test_mark_error(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        db.mark_error("hash_0000", "PDF corrupted")

        record = db.get_record("hash_0000")
        assert record["status"] == "error"
        assert "corrupted" in record["error_message"]

    def test_requeue_for_fallback(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        db.requeue_for_fallback("hash_0000")

        fallback = db.get_fallback_queue()
        assert len(fallback) == 1
        assert fallback[0]["file_id"] == "hash_0000"


class TestJobManagement:
    """Test job creation and completion."""

    def test_create_job(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        job_id = db.create_job("/docs", "{}")
        assert len(job_id) == 12

    def test_complete_job(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        job_id = db.create_job("/docs")
        db.complete_job(job_id)

    def test_get_latest_job_id(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        job_id = db.create_job("/docs")
        assert db.get_latest_job_id() == job_id

    def test_no_latest_job(self, db):
        assert db.get_latest_job_id() is None


class TestStats:
    """Test statistics and progress queries."""

    def test_progress_stats(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        stats = db.get_progress_stats()
        assert stats["total"] == 5
        assert stats["pending"] == 5
        assert stats["complete"] == 0

    def test_final_stats(self, db, sample_pending):
        db.insert_pending_documents(sample_pending)
        stats = db.get_final_stats()
        assert "strategies" in stats
        assert "avg_processing_ms" in stats
