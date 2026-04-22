"""
Tests for the data ingestion pipeline (scripts/ingest_data.py).

These tests validate each stage of the pipeline independently using
mock data — no network calls, no API keys, no ChromaDB writes.
"""

import json
import hashlib
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document

# Add project root to path
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.ingest_data import (
    load_url_registry,
    normalise_documents,
    validate_content_quality,
    compute_content_hash,
    chunk_documents,
)
from config.settings import URL_REGISTRY_PATH


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_registry_entry():
    return {
        "url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        "scheme_name": "HDFC Mid Cap Opportunities Fund",
        "scheme_id": "hdfc-mid-cap-fund-direct-growth",
        "amc": "HDFC Mutual Fund",
        "source_type": "groww_scheme_page",
    }


@pytest.fixture
def sample_document():
    """A realistic document that would pass quality validation."""
    return Document(
        page_content=(
            "HDFC Mid Cap Opportunities Fund Direct Growth\n"
            "NAV: ₹152.34 as on 20 Apr 2026\n"
            "Expense Ratio: 0.74% (Direct Plan)\n"
            "Exit Load: 1% if redeemed within 1 year\n"
            "Minimum SIP: ₹500\n"
            "Fund Size (AUM): ₹42,567 Cr\n"
            "Benchmark: Nifty Midcap 150 TRI\n"
            "Riskometer: Very High\n"
            "The fund invests in mid-cap companies with strong growth potential. "
            "Holdings include a diversified portfolio across sectors. "
            "Returns have been consistent over the long term.\n"
            "Investment Objective: To generate long-term capital appreciation from "
            "a portfolio that is substantially constituted of equity and equity related "
            "securities of mid cap companies.\n"
            "Fund Manager: Chirag Setalvad\n"
            "Inception Date: 25 Jun 2007\n"
        ),
        metadata={
            "source": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
            "registry": {
                "url": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
                "scheme_name": "HDFC Mid Cap Opportunities Fund",
                "scheme_id": "hdfc-mid-cap-fund-direct-growth",
                "amc": "HDFC Mutual Fund",
                "source_type": "groww_scheme_page",
            },
        },
    )


@pytest.fixture
def short_document():
    """A document that is too short to pass quality validation."""
    return Document(
        page_content="Error 404 Not Found",
        metadata={"source": "https://example.com/missing"},
    )


@pytest.fixture
def no_keywords_document():
    """A long document with no financial keywords — should be rejected."""
    return Document(
        page_content="Hello world. " * 100,  # Long enough but irrelevant
        metadata={"source": "https://example.com/irrelevant"},
    )


# ─── Test: URL Registry ──────────────────────────────────────────────────────

class TestURLRegistry:

    def test_url_registry_file_exists(self):
        """config/url_registry.json must exist."""
        assert URL_REGISTRY_PATH.exists(), (
            f"URL registry not found at {URL_REGISTRY_PATH}"
        )

    def test_url_registry_is_valid_json(self):
        """Registry must be parseable JSON."""
        with open(URL_REGISTRY_PATH) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_url_registry_has_entries(self):
        """Registry must have at least one scheme entry."""
        with open(URL_REGISTRY_PATH) as f:
            data = json.load(f)
        assert len(data) >= 1

    def test_url_registry_entries_have_required_fields(self):
        """Each entry must have url, scheme_name, scheme_id, amc, source_type."""
        with open(URL_REGISTRY_PATH) as f:
            data = json.load(f)
        required = ["url", "scheme_name", "scheme_id", "amc", "source_type"]
        for entry in data:
            for field in required:
                assert field in entry, f"Missing '{field}' in entry: {entry}"

    def test_load_url_registry_returns_list(self):
        """load_url_registry() should return a list of dicts."""
        registry = load_url_registry()
        assert isinstance(registry, list)
        assert len(registry) >= 1
        assert "url" in registry[0]


# ─── Test: Content Quality Validation ─────────────────────────────────────────

class TestContentQuality:

    def test_valid_document_passes(self, sample_document):
        """A well-formed financial document should pass quality checks."""
        passed, rejections = validate_content_quality([sample_document])
        assert len(passed) == 1
        assert len(rejections) == 0

    def test_short_document_rejected(self, short_document):
        """Documents below MIN_CONTENT_LENGTH should be rejected."""
        passed, rejections = validate_content_quality([short_document])
        assert len(passed) == 0
        assert len(rejections) == 1
        assert "too short" in rejections[0]

    def test_no_keywords_document_rejected(self, no_keywords_document):
        """Documents without financial keywords should be rejected."""
        passed, rejections = validate_content_quality([no_keywords_document])
        assert len(passed) == 0
        assert len(rejections) == 1
        assert "keywords" in rejections[0].lower()

    def test_mixed_batch(self, sample_document, short_document):
        """A batch with mixed quality should pass valid and reject invalid."""
        passed, rejections = validate_content_quality(
            [sample_document, short_document]
        )
        assert len(passed) == 1
        assert len(rejections) == 1


# ─── Test: Content Hashing ────────────────────────────────────────────────────

class TestContentHashing:

    def test_hash_is_deterministic(self):
        """Same text must produce the same hash."""
        text = "HDFC Mid Cap Fund NAV 152.34"
        assert compute_content_hash(text) == compute_content_hash(text)

    def test_hash_changes_on_content_change(self):
        """Different text must produce different hashes."""
        hash1 = compute_content_hash("NAV: 152.34")
        hash2 = compute_content_hash("NAV: 155.67")
        assert hash1 != hash2

    def test_hash_is_sha256(self):
        """Hash output must be a valid 64-character hex string (SHA-256)."""
        h = compute_content_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ─── Test: Chunking ───────────────────────────────────────────────────────────

class TestChunking:

    def test_long_document_produces_multiple_chunks(self, sample_document):
        """A document longer than chunk_size should produce multiple chunks."""
        # Make the document much longer
        sample_document.page_content = sample_document.page_content * 10
        chunks = chunk_documents([sample_document])
        assert len(chunks) > 1

    def test_chunks_preserve_metadata(self, sample_document):
        """Each chunk should carry the parent document's metadata."""
        sample_document.page_content = sample_document.page_content * 10
        chunks = chunk_documents([sample_document])
        for chunk in chunks:
            assert "source" in chunk.metadata

    def test_short_document_produces_single_chunk(self):
        """A short document should remain as a single chunk."""
        doc = Document(
            page_content="NAV is 150.",
            metadata={"source": "test"},
        )
        chunks = chunk_documents([doc])
        assert len(chunks) == 1
