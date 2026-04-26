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

# CORS — simplified for local/cloud flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Welcome message to confirm backend is reachable."""
    return {
        "message": "groww-factor RAG API is alive and reachable.",
        "endpoints": ["/chat (POST)", "/health (GET)"],
        "status": "online"
    }


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
        "version": "2.1.0",
    }


@app.post("/admin/ingest")
async def trigger_ingestion(token: str = None):
    """
    Protected endpoint to trigger the RAG ingestion pipeline.
    Expected to be called by GitHub Actions daily.
    """
    expected_token = os.getenv("ADMIN_SECRET_KEY")
    if not expected_token or token != expected_token:
        logger.warning(f"Unauthorized ingestion attempt with token: {token}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    from orchestrator.run_pipeline import run_ingestion
    from starlette.concurrency import run_in_threadpool
    try:
        logger.info("Starting remote ingestion trigger (in threadpool)...")
        # Running in a threadpool solves the Playwright Sync vs Asyncio conflict
        stats = await run_in_threadpool(run_ingestion, force=True)
        return {"status": "success", "stats": stats}
    except Exception as e:
        logger.exception("Remote ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Lightweight endpoint for keep-alive pings."""
    return {"status": "alive", "timestamp": datetime.datetime.now().isoformat()}

# ─── Entry Point ──────────────────────────────────────────────────────────────

import asyncio

async def continuous_sync_task():
    """
    Background loop that keeps the system updated every 24 hours
    without needing manual intervention.
    """
    while True:
        # Sleep for 24 hours (86400 seconds)
        await asyncio.sleep(86400)
        logger.info("🕒 Scheduled 24-hour sync starting...")
        try:
            from orchestrator.run_pipeline import run_ingestion
            run_ingestion()
            logger.info("✅ Scheduled sync complete.")
        except Exception as e:
            logger.error(f"❌ Scheduled sync failed: {e}")

@app.on_event("startup")
async def startup_event():
    """
    STABILITY PROTOCOL: Ensure vector store is healthy and hydrated.
    If corrupted (common on Render reboots), we wipe and rebuild.
    """
    logger.info("🛠️ Running Stability Handshake...")
    from core.vector_store import get_vector_store
    import shutil
    from pathlib import Path
    
    db_path = Path("./chroma_db")
    
    try:
        # 1. Attempt to connect and check health
        vs = get_vector_store()
        count = vs._collection.count()
        logger.info(f"💾 Database identified: {count} documents.")
        
        # 2. If empty, trigger hydration
        if count == 0:
            raise ValueError("Empty database detected.")
            
    except Exception as e:
        logger.warning(f"⚠️ Stability Check Failed: {e}")
        logger.info("🔄 RECOVERY: Wiping and Re-hydrating Fact Base...")
        
        # 3. Wipe and Rebuild (The 'Nuke' Option for stability)
        if db_path.exists():
            shutil.rmtree(db_path)
        
        try:
            from orchestrator.run_pipeline import run_ingestion
            run_ingestion(force=True)
            logger.info("🚀 Recovery complete. Fact Base is live.")
        except Exception as ingest_error:
            logger.error(f"❌ CRITICAL: Recovery failed: {ingest_error}")

    # Start the continuous background sync (24h loop)
    import asyncio
    asyncio.create_task(continuous_sync_task())
    logger.info("✅ System is online and self-healing.")

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting API on {API_HOST}:{API_PORT}")
    uvicorn.run(app, host=API_HOST, port=API_PORT)
