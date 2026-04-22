"""
Tests for the retrieval layer (core/retriever.py).

Tests the caching behaviour and configuration — no ChromaDB or API
calls required (all mocked).
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from core.retriever import invalidate_retriever_cache


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cache Behaviour
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRetrieverCache:

    def test_invalidate_cache_resets_globals(self):
        """invalidate_retriever_cache() should reset the module-level cache."""
        import core.retriever as mod
        # Set fake cached values
        mod._cached_retriever = "fake"
        mod._cached_vector_retriever = "fake"

        invalidate_retriever_cache()

        assert mod._cached_retriever is None
        assert mod._cached_vector_retriever is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRetrieverConfig:

    def test_chroma_path_from_settings(self):
        """The retriever should use CHROMA_PERSIST_DIR from settings."""
        from config.settings import CHROMA_PERSIST_DIR
        # Just verify the setting is loadable and has a sane default
        assert CHROMA_PERSIST_DIR is not None
        assert "chroma" in CHROMA_PERSIST_DIR.lower()

    def test_weights_from_settings(self):
        """Vector and BM25 weights should sum to 1.0."""
        from config.settings import VECTOR_WEIGHT, BM25_WEIGHT
        assert VECTOR_WEIGHT + BM25_WEIGHT == pytest.approx(1.0)

    def test_search_k_values(self):
        """Search k values should be positive integers."""
        from config.settings import VECTOR_SEARCH_K, BM25_SEARCH_K
        assert VECTOR_SEARCH_K > 0
        assert BM25_SEARCH_K > 0
        assert isinstance(VECTOR_SEARCH_K, int)
        assert isinstance(BM25_SEARCH_K, int)
