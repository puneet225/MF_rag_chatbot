#!/usr/bin/env bash
# groww-factor — Render Start Orchestrator
# ========================================
# This script handles the multi-stage boot sequence required for 
# a compliance-first RAG system on Render's ephemeral free tier.

set -e # Exit on any error

echo "🚀 Starting groww-factor boot sequence..."

# 1. Initial Data Ingestion (Background)
# -------------------------
# Ensures that even on a fresh cold-boot, the vector store
# is populated. We run this in the background so the server can bind
# to the port immediately and pass Render's health check.
echo "[Stage 1/2] Launching initial data ingestion in background..."
python orchestrator/run_pipeline.py &

# 2. FastAPI Server
# -----------------
# Boot the FastAPI server using Uvicorn.
# We bind to 0.0.0.0 and use the dynamic $PORT assigned by Render.
echo "[Stage 2/2] Booting FastAPI server on port ${PORT:-8001}..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}
