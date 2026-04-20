"""
Core RAG pipeline modules.

Each module implements one phase of the LangGraph pipeline:
  - intent_classifier.py  — Phase 5.1: Intent classification node
  - pii_guard.py          — Phase 7.2: PII detection (standalone, testable)
  - refusal.py            — Phase 7.1: Refusal + greeting handlers
  - retriever.py          — Phase 5.3: Hybrid retrieval (vector + BM25)
  - generator.py          — Phase 6:   Generation with post-validation
  - graph.py              — Pipeline assembly (LangGraph StateGraph)
  - state.py              — Shared state schema (ChatState TypedDict)
"""
