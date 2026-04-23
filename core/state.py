"""
LangGraph State Schema
======================

Defines the shared state that flows through every node in the
LangGraph pipeline. Each node reads from and writes to this TypedDict.

State flow:
  START → classify_intent (writes: intent)
        → safety_guard   (writes: intent, response — if PII detected)
        → [routing based on intent]
            → greeting    (writes: response)
            → refusal     (writes: response, citation)
            → retrieval   (writes: retrieved_docs, citation)
                → generation (writes: response)
        → END
"""

from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    """
    Shared state for the Mutual Fund FAQ LangGraph pipeline.

    Attributes:
        messages:         Full conversation history for the thread.
                          Managed by LangGraph's add_messages reducer —
                          new messages are appended, not replaced.

        intent:           Classification of the current user query.
                          Set by classify_intent_node or overridden by
                          safety_guard_node on PII detection.
                          Values: "factual" | "advisory" | "greeting" | "privacy_risk"

        retrieved_docs:   List of chunk dicts from ChromaDB, set by retrieval_node.
                          Each dict has "page_content" and "metadata" keys.

        identified_scheme: Scheme name if resolved from the query (e.g., via
                          dictionary matching against the URL registry).
                          Currently unused by nodes — reserved for future
                          metadata-filtered retrieval.

        response:         Final assistant response text to return to the user,
                          including the citation footer.

        citation:         Single source URL for the response footer.
                          Set by retrieval_node from the top retrieved chunk's
                          source metadata.
    """

    messages: Annotated[List[BaseMessage], add_messages]
    intent: str
    retrieved_docs: List[dict]
    identified_scheme: str
    rewritten_query: str
    response: str
    citation: str
