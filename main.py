"""
HDFC Mutual Fund RAG API
========================

FastAPI application that exposes the LangGraph pipeline as a REST API.

Endpoints:
  POST /chat     — Send a user message, get a facts-only response.
  GET  /health   — Liveness probe.

Environment:
  GOOGLE_API_KEY — Required. Google AI API key for Gemini models.
  API_HOST       — Optional. Default: 0.0.0.0
  API_PORT       — Optional. Default: 8001
"""

import os
import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from config.settings import API_HOST, API_PORT
from core.graph import app_graph
from langchain_core.messages import HumanMessage

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api")

# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="groww-factor RAG API",
    description="Compliance-first factual intelligence for mutual fund analysis.",
    version="2.1.0",
)

# CORS — allow the Next.js frontend from any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Schemas ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming user message."""
    message: str
    thread_id: Optional[str] = "default_user"


class ChatResponse(BaseModel):
    """Outgoing assistant response."""
    response: str
    intent: str
    citation: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Process a user message through the LangGraph pipeline.

    Flow: classify_intent → safety_guard → [route] → response
    """
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] POST /chat — message={request.message!r}")

    # Pre-flight: API key check
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error(f"[{request_id}] GOOGLE_API_KEY missing")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error. Please contact the administrator.",
        )

    try:
        # LangGraph config — thread persistence keyed by thread_id
        config = {"configurable": {"thread_id": request.thread_id}}

        # Prepare input state
        input_state = {
            "messages": [HumanMessage(content=request.message)]
        }

        # Invoke the graph
        logger.info(f"[{request_id}] Invoking LangGraph (thread={request.thread_id})")
        result = app_graph.invoke(input_state, config)
        logger.info(f"[{request_id}] Graph complete — intent={result.get('intent')}")

        # Extract response fields from final state
        response_text = result.get(
            "response",
            "I could not process that request. Please try again.",
        )
        intent = result.get("intent", "unknown")
        citation = result.get("citation", "")

        return ChatResponse(
            response=response_text,
            intent=intent,
            citation=citation,
        )

    except Exception as e:
        # Log full traceback server-side, but don't leak it to the client
        logger.exception(f"[{request_id}] Unhandled error in /chat")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        )


@app.get("/health")
async def health_check():
    """Liveness probe for Docker and load balancers."""
    return {
        "status": "ok",
        "service": "HDFC Mutual Fund RAG API",
        "version": "2.0.0",
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting API on {API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT)
