"""
Phase 5.3 — Hybrid Retrieval Layer
===================================

Builds and returns a cached EnsembleRetriever combining:
  - Dense vector search (60% weight) via ChromaDB + Gemini Embedding
  - Keyword search (40% weight) via BM25

Key improvements over the original implementation:
  1. BM25 index is cached at module level — not rebuilt on every query.
  2. ChromaDB path is configurable via CHROMA_PERSIST_DIR env var.
  3. An invalidation function is exposed so the ingestion script can
     signal a refresh after re-indexing.

Usage:
  from core.retriever import get_retriever, invalidate_retriever_cache

  retriever = get_retriever()                 # cached singleton
  docs = retriever.invoke("expense ratio?")
  invalidate_retriever_cache()                # after re-ingestion
"""

import os
import logging
from typing import Optional

from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from core.vector_store import get_vector_store
from config.settings import (
    VECTOR_SEARCH_K,
    BM25_SEARCH_K,
    VECTOR_WEIGHT,
    BM25_WEIGHT,
)

logger = logging.getLogger("retriever")

# ─── Module-Level Cache ───────────────────────────────────────────────────────
_cached_retriever: Optional[EnsembleRetriever] = None
_cached_vector_retriever = None


def invalidate_retriever_cache() -> None:
    """
    Clear the cached retriever so the next call to get_retriever()
    rebuilds it from the current ChromaDB state.

    Call this after the ingestion script updates the vector DB.
    """
    global _cached_retriever, _cached_vector_retriever
    _cached_retriever = None
    _cached_vector_retriever = None
    logger.info("Retriever cache invalidated — will rebuild on next query.")


def _build_vector_retriever():
    """Build the dense vector retriever from the configured storage."""
    vectorstore = get_vector_store()
    return vectorstore, vectorstore.as_retriever(
        search_kwargs={"k": VECTOR_SEARCH_K}
    )


def _build_bm25_retriever(vectorstore):
    """
    Build BM25 retriever from all documents in ChromaDB.

    NOTE: This loads all documents into memory. Acceptable for the current
    corpus size (~500 chunks). For larger corpora, consider persisting the
    BM25 index to disk.
    """
    result = vectorstore.get()
    all_docs = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    if not all_docs:
        logger.warning("No documents in ChromaDB — BM25 retriever will be empty.")
        return None

    docs = [
        Document(page_content=doc, metadata=meta)
        for doc, meta in zip(all_docs, metadatas)
    ]

    bm25 = BM25Retriever.from_documents(docs)
    bm25.k = BM25_SEARCH_K
    logger.info(f"BM25 index built with {len(docs)} documents.")

    return bm25


def get_retriever():
    """
    Return a cached hybrid (vector + BM25) retriever.

    The retriever is built once and cached at module level. Subsequent
    calls return the same instance. Call invalidate_retriever_cache()
    after re-ingestion to force a rebuild.

    Returns:
        EnsembleRetriever if BM25 can be built, else a pure vector retriever.
    """
    global _cached_retriever, _cached_vector_retriever

    if _cached_retriever is not None:
        return _cached_retriever

    logger.info("Building retriever (first call or cache invalidated)...")

    vectorstore, vector_retriever = _build_vector_retriever()
    _cached_vector_retriever = vector_retriever

    bm25_retriever = _build_bm25_retriever(vectorstore)

    if bm25_retriever is None:
        logger.warning("Falling back to vector-only retrieval (no BM25).")
        _cached_retriever = vector_retriever
        return _cached_retriever

    ensemble = EnsembleRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        weights=[VECTOR_WEIGHT, BM25_WEIGHT],
    )

    _cached_retriever = ensemble
    logger.info(
        f"Hybrid retriever ready: vector({VECTOR_WEIGHT}) + BM25({BM25_WEIGHT}), "
        f"k={VECTOR_SEARCH_K}/{BM25_SEARCH_K}"
    )

    return _cached_retriever
