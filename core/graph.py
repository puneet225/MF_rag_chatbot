"""
LangGraph Pipeline Assembly
===========================

Assembles the six-node directed graph that powers the FAQ assistant.
Each node is imported from its own dedicated module (one file per phase).

Graph topology:
  START → classify_intent → safety_guard → [conditional routing]
                                              │
                           ┌──────────────────┼──────────────────┐
                           ▼                  ▼                  ▼
                    privacy_risk → END   greeting → END   advisory → refusal → END
                                                                 │
                                                          factual (default)
                                                                 ▼
                                                           retrieval → generation → END

Checkpointer:
  MemorySaver — in-memory per-thread persistence. Suitable for
  single-process development. For production, swap for SqliteSaver
  or PostgresSaver.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from core.state import ChatState
from core.intent_classifier import classify_intent_node
from core.pii_guard import detect_pii
from core.refusal import refusal_node, greeting_node
from core.generator import retrieval_node, generation_node

# ─── Typing ───────────────────────────────────────────────────────────────────
from typing import Dict, Any


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Safety Guard Node (uses core.pii_guard for detection)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def safety_guard_node(state: ChatState) -> Dict[str, Any]:
    """
    LangGraph node: Scan the latest user message for PII.

    If PII is detected, overrides the intent to 'privacy_risk' and sets
    a blocking response. Otherwise, passes state through unchanged.

    This node runs AFTER intent classification but BEFORE routing,
    so it can override any intent when PII is found.
    """
    last_message = state["messages"][-1].content
    detections = detect_pii(last_message)

    if detections:
        # Log detection types (NOT the matched values)
        detected_types = [d["label"] for d in detections]
        return {
            "intent": "privacy_risk",
            "response": (
                "⚠️ I detected potentially sensitive information "
                f"({', '.join(detected_types)}). "
                "For your security, please do not share personal identifiers. "
                "I cannot process this request."
            ),
        }

    return {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Conditional Router
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def route_after_safety(state: ChatState) -> str:
    """
    Route the pipeline based on the current intent.

    Returns the name of the next node (or END for privacy_risk).
    """
    intent = state.get("intent", "factual")

    if intent == "privacy_risk":
        return END
    if intent == "greeting":
        return "greeting"
    if intent == "advisory":
        return "refusal"
    return "retrieval"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Graph Factory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def create_graph():
    """
    Build and compile the LangGraph state machine.

    Nodes:
      1. classify_intent  — core/intent_classifier.py
      2. safety_guard     — this file (uses core/pii_guard.py)
      3. greeting         — core/refusal.py
      4. refusal          — core/refusal.py
      5. retrieval        — core/generator.py
      6. generation       — core/generator.py
    """
    workflow = StateGraph(ChatState)

    # Register nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("safety_guard", safety_guard_node)
    workflow.add_node("greeting", greeting_node)
    workflow.add_node("refusal", refusal_node)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("generation", generation_node)

    # Linear edges
    workflow.add_edge(START, "classify_intent")
    workflow.add_edge("classify_intent", "safety_guard")

    # Conditional routing after safety guard
    workflow.add_conditional_edges(
        "safety_guard",
        route_after_safety,
        {
            END: END,
            "greeting": "greeting",
            "refusal": "refusal",
            "retrieval": "retrieval",
        },
    )

    # Terminal edges
    workflow.add_edge("retrieval", "generation")
    workflow.add_edge("generation", END)
    workflow.add_edge("greeting", END)
    workflow.add_edge("refusal", END)

    # Compile with in-memory checkpointer for thread persistence
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# ─── Singleton graph instance (imported by main.py) ──────────────────────────
app_graph = create_graph()
