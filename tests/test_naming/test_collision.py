"""Tests for collision resolution strategies."""

from docforge.naming.collision import CollisionResolver


class TestCollisionResolver:
    """Test filename collision resolution."""

    def test_suffix_strategy(self):
        resolver = CollisionResolver(strategy="suffix")
        # First call should return the name as-is
        name1 = resolver.resolve("report.pdf", "id1")
        assert name1 == "report.pdf"

    def test_hash_strategy(self):
        resolver = CollisionResolver(strategy="hash")
        name = resolver.resolve("report.pdf", "id1")
        assert name.endswith(".pdf")
