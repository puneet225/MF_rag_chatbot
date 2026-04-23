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

Groww-Factor uses a **Unified Ingestion Pipeline** (Orchestrator) to fetch and "Mirror" fund details. It utilizes:
- **Google Cloud Embeddings**: (`models/gemini-embedding-001`) for high-speed, zero-compilation factual indexing.
- **LangGraph Controller**: To process user intent and ensure "Digital Mirror" factual alignment.
- **ChromaDB**: For pinpoint-accurate document retrieval.

## 🌐 Production Deployment

### Render (Backend) Setup
For a successful deployment on Render, add the following Environment Variables:
- `GOOGLE_API_KEY`: Your Google AI Gemini key.
- `ADMIN_SECRET_KEY`: Security token for ingestion (e.g., `secret`).
- `INGEST_TOKEN`: Token for automated sync.
- `PORT`: **`8010`** (Matches internal app routing).

### Vercel (Frontend) Setup
- `NEXT_PUBLIC_API_URL`: Your live Render URL (e.g., `https://groww-factor.onrender.com`).

---
*Disclaimer: Groww-Factor provides data sourced from AMC portals. It is a factual assistant and does not provide investment advisory services.*
