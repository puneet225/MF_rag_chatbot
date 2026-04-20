"""
Phase 7.1 — Refusal & Greeting Handlers
========================================

Static response nodes for non-factual query paths. These nodes do NOT
invoke the LLM or the retriever — they return templated responses only.

Nodes:
  - refusal_node:  Advisory / comparative queries → polite refusal + AMFI link
  - greeting_node: Greetings → welcome message listing capabilities
"""

from typing import Dict, Any

from config.settings import AMFI_EDUCATION_URL
from core.state import ChatState


def refusal_node(state: ChatState) -> Dict[str, Any]:
    """
    LangGraph node: Handle advisory queries with a compliant refusal.

    No retrieval or LLM call occurs. Returns a static message pointing
    the user to AMFI's investor education portal.

    Reads:  (nothing — triggered by routing)
    Writes: state["response"], state["citation"]
    """
    return {
        "response": (
            "I am a facts-only assistant and cannot provide investment advice, "
            "opinions, or fund recommendations. For guidance on mutual fund "
            "investing, please refer to the official "
            f"[AMFI Investor Education]({AMFI_EDUCATION_URL}) portal."
        ),
        "citation": AMFI_EDUCATION_URL,
    }


def greeting_node(state: ChatState) -> Dict[str, Any]:
    """
    LangGraph node: Handle general greetings with a welcome message.

    No retrieval or LLM call occurs. Returns a static message listing
    the assistant's capabilities.

    Reads:  (nothing — triggered by routing)
    Writes: state["response"]
    """
    return {
        "response": (
            "Hello! I am your HDFC Mutual Fund FAQ assistant. "
            "I can provide factual information like expense ratios, "
            "exit loads, NAV, minimum SIP amounts, fund managers, "
            "and benchmark details for specific HDFC schemes. "
            "How can I help you today?"
        ),
    }
