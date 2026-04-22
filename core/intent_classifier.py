"""
Phase 5.1 — Intent Classification Node
=======================================

Classifies the user's query into one of four intent categories using
Gemini Flash zero-shot classification. This is the first node in the
LangGraph pipeline — it determines the entire routing path.

Intent categories:
  - 'factual':      Objective queries about fund details → retrieval path
  - 'advisory':     Investment advice / comparisons → refusal path
  - 'greeting':     General greetings / polite conversation → greeting path
  - 'privacy_risk': Contains sensitive PII → blocked immediately

The classification runs BEFORE any retrieval or LLM generation occurs,
so advisory and PII queries never touch the vector store.
"""

from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from config.settings import LLM_MODEL, LLM_TEMPERATURE
from core.state import ChatState


# ─── LLM Instance (shared across calls within the same process) ───────────────
_llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=LLM_TEMPERATURE)

# ─── Classification Prompt ────────────────────────────────────────────────────
_INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a classifier for a Mutual Fund FAQ Assistant.
Classify the user's query into one of these categories:

- 'factual': Objective queries about fund details (expense ratio, exit load, NAV, SIP, AUM, benchmark, riskometer, fund manager, holdings, portfolio, returns history, etc.)
- 'advisory': Queries asking for investment advice, recommendations, comparisons, or "which is better", "should I invest", personal financial situations
- 'greeting': General greetings, thanks, or polite conversation ("hi", "hello", "thank you")
- 'privacy_risk': Queries containing or requesting sensitive info like PAN, Aadhaar, account numbers, passwords, OTPs

Return ONLY the category name in lowercase. No explanation."""),
    ("human", "{query}")
])


def classify_intent_node(state: ChatState) -> Dict[str, Any]:
    """
    LangGraph node: Classify the latest user message into an intent category.

    Reads:  state["messages"][-1].content
    Writes: state["intent"]
    """
    last_message = state["messages"][-1].content

    chain = _INTENT_PROMPT | _llm
    result = chain.invoke({"query": last_message})
    
    # Handle case where content might be a list (multimodal/new Gemini versions)
    content = result.content
    if isinstance(content, list):
        content = " ".join([c['text'] if isinstance(c, dict) and 'text' in c else str(c) for c in content])
    
    intent = content.strip().lower()

    # Guard against unexpected model output — default to factual
    valid_intents = {"factual", "advisory", "greeting", "privacy_risk"}
    if intent not in valid_intents:
        intent = "factual"

    return {"intent": intent}
