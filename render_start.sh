#!/usr/bin/env bash
# groww-factor — Render Start Orchestrator
# ========================================
# This script handles the multi-stage boot sequence required for 
# a compliance-first RAG system on Render's ephemeral free tier.

set -e # Exit on any error

echo "🚀 Starting groww-factor boot sequence..."

# 1. Initial Data Ingestion
# -------------------------
# Ensures that even on a fresh cold-boot, the ChromaDB vector store
# is populated with the latest facts from the 5 fund sources.
echo "[Stage 1/3] Running initial data ingestion..."
python scripts/ingest_data.py

# 2. Background Scheduler
# -----------------------
# Launches the daily 9:30 AM scheduler in the background.
# This stays alive for the duration of the web service.
echo "[Stage 2/3] Launching daily 9:30 AM scheduler..."
python scripts/scheduled_ingestion.py &

# 3. FastAPI Server
# -----------------
# Finally, boot the FastAPI server using Uvicorn.
# We bind to 0.0.0.0 and use the dynamic $PORT assigned by Render.
echo "[Stage 3/3] Booting FastAPI server on port ${PORT:-8001}..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}
