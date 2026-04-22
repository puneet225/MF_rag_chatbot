# Groww-Factor: Pinpoint Precision RAG for HDFC Mutual Funds 📈

**Groww-Factor** is a high-density Retrieval-Augmented Generation (RAG) assistant designed for 100% factual accuracy in mutual fund data analysis. It acts as a **"Digital Mirror"** of the official AMC fund pages, serving real-time NAV, AUM, and Tax implications without the marketing noise.

## 🏆 Key Features

- **Digital Mirror Precision**: Translates complex JSON fund data into natural language facts, ensuring every answer is explicitly tethered to the latest official source.
- **Master Merge Ingestion**: Harmonizes disparate data sources (Pricing, Fund Stats, Taxation) into single, high-density factual records.
- **Zero-Noise Retrieval**: Implements a recursive deep-purge of marketing boilerplate and historical data, eliminating date-based hallucinations.
- **Production Guardrails**: Strictly minimalist responses—users get exactly the fact they requested, ensuring professional-grade financial transparency.

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python 3.10+
- Node.js (for frontend)
- [Gemini API Key](https://aistudio.google.com/app/apikey)

### 2. Backend Setup
```bash
git clone https://github.com/puneet225/Milestone_1.git
cd Milestone_1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Add GOOGLE_API_KEY and ADMIN_SECRET_KEY to .env
python3 main.py
```

### 3. Frontend Setup
```bash
cd frontend_next_js
npm install
npm run dev
```

## 🏗️ Architecture

Groww-Factor uses a **Unified Ingestion Pipeline** (Orchestrator) to fetch and "Mirror" fund details from official portals. It then utilizes **LangGraph** to process user intent and a **ChromaDB** vector store for pinpoint-accurate document retrieval.

## 🌐 Production Deployment

- **Backend**: Hosted on Render (with automated daily data refresh via GitHub Actions).
- **Frontend**: Hosted on Vercel (proxied to the Render API).

---
*Disclaimer: Groww-Factor provides data sourced from AMC portals. It is a factual assistant and does not provide investment advisory services.*
