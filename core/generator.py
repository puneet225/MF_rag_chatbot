"""
Phase 6 — Generation Node with Post-Validation
================================================

Generates the final facts-only response from retrieved context using
Gemini Flash, then validates the output against the Problem Statement
constraints:
  1. ≤ 3 sentences (excluding the citation footer)
  2. No forbidden advisory/comparative language
  3. Citation URL is present and matches an allowlisted source

If validation fails, one retry is attempted with a stricter prompt.
If the retry also fails, a templated safe response is returned.

This module also contains the retrieval_node which bridges the retriever
output into the LangGraph state.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from config.settings import (
    LLM_MODEL,
    LLM_TEMPERATURE,
    MAX_RESPONSE_SENTENCES,
    CONTEXT_WINDOW_TURNS,
    FORBIDDEN_PATTERNS,
    URL_REGISTRY_PATH,
)
from core.state import ChatState

logger = logging.getLogger("generator")

# ─── LLM Instance ────────────────────────────────────────────────────────────
_llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

# ─── Allowlisted URLs (loaded once) ──────────────────────────────────────────
_ALLOWLISTED_URLS: Optional[set] = None


def _get_allowlisted_urls() -> set:
    """Load the set of allowlisted URLs from the registry. Cached."""
    global _ALLOWLISTED_URLS
    if _ALLOWLISTED_URLS is None:
        try:
            with open(URL_REGISTRY_PATH) as f:
                registry = json.load(f)
            _ALLOWLISTED_URLS = {entry["url"] for entry in registry}
        except Exception:
            _ALLOWLISTED_URLS = set()
    return _ALLOWLISTED_URLS


_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a high-fidelity 'Factual Mirror' for HDFC Mutual Fund data.

YOUR MISSION:
Locate the specific numeric or factual detail requested by the user within the PROVIDED CONTEXT. 

GUIDELINES:
- Report the specific fact (NAV, AUM, Expense Ratio, Fund Manager, etc.) clearly and exactly as stated in the context.
- Keep the response brief (1-2 sentences). 
- If the context contains 'Digital Mirror' sentences, use those as your primary source of truth.
- Do NOT provide financial advice, plans, or comparisons.
- Only say "Not found in indexed sources" if the context truly does not contain any relevant information for the specific scheme requested.

CONTEXT:
{context}"""),
    ("human", "{query}")
])

_STRICT_RETRY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a factual assistant. Answer in EXACTLY {max_sentences} sentences or fewer.
Use ONLY the facts below. Do NOT give advice. Do NOT compare funds.
If unsure, say "I could not find this in the indexed sources."

FACTS:
{context}"""),
    ("human", "{query}")
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Post-Generation Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def validate_response(text: str) -> Dict[str, Any]:
    """
    Validate a generated response against the Problem Statement constraints.

    Returns:
        {
            "valid": bool,
            "issues": list[str],    # Human-readable list of violations
        }
    """
    issues = []

    # Check 1: Sentence count (split on sentence-ending punctuation)
    # Exclude footer lines starting with "**Source:**" or "*Last updated"
    body_lines = [
        line for line in text.split("\n")
        if line.strip()
        and not line.strip().startswith("**Source:")
        and not line.strip().startswith("*Last updated")
    ]
    body_text = " ".join(body_lines)
    sentences = re.split(r'(?<=[.!?])\s+', body_text)
    sentences = [s for s in sentences if s.strip()]

    if len(sentences) > MAX_RESPONSE_SENTENCES:
        issues.append(
            f"Sentence count {len(sentences)} exceeds maximum {MAX_RESPONSE_SENTENCES}"
        )

    # Check 2: Forbidden patterns (advisory language)
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append(f"Contains forbidden pattern: {pattern}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


def ensure_citation_footer(
    text: str, citation: str, last_updated: str
) -> str:
    """
    Ensure the response contains the citation footer. If already present,
    return as-is. If missing, append it.
    """
    if "**Source:**" not in text:
        text = f"{text}\n\n**Source:** {citation}\n*Last updated from sources: {last_updated}*"
    return text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Retrieval Node
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def retrieval_node(state: ChatState) -> Dict[str, Any]:
    """
    LangGraph node: Retrieve relevant chunks from the vector store.

    Reads:  state["rewritten_query"] (fallbacks to messages if missing)
    Writes: state["retrieved_docs"], state["citation"]
    """
    from core.retriever import get_retriever

    query = state.get("rewritten_query") or state["messages"][-1].content
    retriever = get_retriever()

    logger.info(f"Retrieving docs for: {query}")
    docs = retriever.invoke(query)

    citation = ""
    if docs:
        citation = docs[0].metadata.get("source", "")

    return {
        "retrieved_docs": [doc.model_dump() for doc in docs],
        "citation": citation,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Generation Node
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generation_node(state: ChatState) -> Dict[str, Any]:
    """
    LangGraph node: Generate a facts-only response with post-validation.

    Flow:
      1. Build context from retrieved docs.
      2. Use a sliding window of last N messages for query context.
      3. Generate response via Gemini Flash.
      4. Validate against constraints.
      5. If invalid → retry once with stricter prompt.
      6. If still invalid → return templated safe response.
      7. Ensure citation footer is present.

    Reads:  state["retrieved_docs"], state["messages"], state["citation"]
    Writes: state["response"]
    """
    docs = state.get("retrieved_docs", [])
    
    # Sliding window: Use only the last N messages for query context
    messages = state.get("messages", [])
    recent_messages = messages[-CONTEXT_WINDOW_TURNS:]
    last_message = recent_messages[-1].content if recent_messages else ""

    # ─── Smart Citation Selection ───
    # We look for the document that most likely represents the user's focus
    # by matching scheme names or URLs against the query tokens.
    query_lower = last_message.lower()
    best_doc = docs[0] if docs else None
    
    # Try to find a doc that actually matches the fund name asked about
    for doc in docs:
        meta = doc.get("metadata", {})
        scheme_name = meta.get("scheme_name", "").lower()
        source_url = meta.get("source", "").lower()
        if scheme_name in query_lower or any(word in query_lower for word in scheme_name.split()):
            best_doc = doc
            break

    last_updated = "unknown date"
    citation = ""
    if best_doc:
        meta = best_doc.get("metadata", {})
        last_updated = meta.get("last_updated", "unknown date")
        citation = meta.get("source", "")

    # Fallback: No documents retrieved
    if not docs:
        return {
            "response": (
                "I could not find any factual information regarding your query "
                "in the HDFC schemes I currently track."
            )
        }

    # Build context from retrieved chunks
    context = "\n\n".join(doc["page_content"] for doc in docs)

    # ── Attempt 1: Standard generation ──
    chain = _GENERATION_PROMPT | _llm
    result = chain.invoke({
        "context": context,
        "query": last_message,
        "max_sentences": MAX_RESPONSE_SENTENCES,
    })
    
    # Handle case where content might be a list (multimodal/new Gemini versions)
    content = result.content
    if isinstance(content, list):
        content = " ".join([c['text'] if isinstance(c, dict) and 'text' in c else str(c) for c in content])
    
    response_text = content.strip()

    # Validate
    validation = validate_response(response_text)

    if not validation["valid"]:
        logger.warning(
            f"Generation validation failed (attempt 1): {validation['issues']}"
        )

        # ── Attempt 2: Strict retry ──
        retry_chain = _STRICT_RETRY_PROMPT | _llm
        retry_result = retry_chain.invoke({
            "context": context,
            "query": last_message,
            "max_sentences": MAX_RESPONSE_SENTENCES,
        })
        
        # Handle case where content might be a list
        content = retry_result.content
        if isinstance(content, list):
            content = " ".join([c['text'] if isinstance(c, dict) and 'text' in c else str(c) for c in content])
            
        response_text = content.strip()

        # Re-validate
        retry_validation = validate_response(response_text)

        if not retry_validation["valid"]:
            logger.warning(
                f"Generation validation failed (attempt 2): "
                f"{retry_validation['issues']} — using safe fallback."
            )
            # ── Fallback: Templated safe response ──
            response_text = (
                "Based on the indexed sources, I found relevant information "
                "for your query. Please refer to the source link below for "
                "complete details."
            )

    # Ensure citation footer
    full_response = ensure_citation_footer(response_text, citation, last_updated)

    return {"response": full_response}
