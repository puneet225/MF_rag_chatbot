# 🚀 groww-factor: Compliance-First Mutual Fund RAG

[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js-000000?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-FF6F00?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![VectorDB](https://img.shields.io/badge/VectorDB-Chroma-336791?style=flat-square)](https://docs.trychroma.com/)

**groww-factor** is a production-grade Retrieval-Augmented Generation (RAG) assistant designed for the HDFC Mutual Fund ecosystem. It prioritises **regulatory compliance**, **factual accuracy**, and **PII security** over open-ended conversation.

---

## 🌌 The Experience

Featuring a premium **twinkling space-themed UI** with glassmorphism effects, `groww-factor` provides a stunning, responsive experience for analyzing fund data.

> [!TIP]
> Ask about expense ratios, fund managers, exit loads, or NAVs. Try asking for "investment advice" to see the compliance safety guards in action!

---

## 🛠️ System Lifecycle & Architecture

The following diagram illustrates the complete end-to-end flow of the **groww-factor** system, from data ingestion to live user serving.

```mermaid
flowchart TD
    subgraph Local["Data Ingestion & Master Orchestrator (Local/GitHub)"]
        direction TB
        P1[Phase 1: Scraper] --> P2[Phase 2: Normalizer]
        P2 --> P3[Phase 3: Chunker]
        P3 --> P4[Phase 4: Vector Store]
        
        DB_Local[(Local ChromaDB)]
        P4 -- "Update/Sync" --> DB_Local
        
        GH[GitHub Repository]
        P4 -- "Auto-Commit State" --> GH
    end

    subgraph Cloud["Production Deployment (Cloud Runtime)"]
        direction TB
        Vercel[Vercel Frontend]
        Render[Render Backend]
        Gemini[Google Gemini 1.5 Flash]
        DB_Cloud[(ChromaDB Instance)]
        
        GH -- "Auto-Deploy" --> Vercel
        GH -- "Auto-Deploy" --> Render
        
        Render -- "Query" --> DB_Cloud
        Render -- "Inference" --> Gemini
    end

    User((User)) -- "HTTPS" --> Vercel
    Vercel -- "API Proxy" --> Render
```

---

## 🔒 Key Features

- **🛡️ PII Firewall:** Standalone regex-driven guard catching PAN, Aadhaar, Emails, and Bank details before they hit the LLM.
- **⚖️ Compliance Post-Check:** Every response is validated against 10+ forbidden advisory patterns (e.g., "I recommend", "buy", "better than").
- **⚡ Hybrid Retrieval:** 60% Dense Vector / 40% BM25 Keyword search for precise numerical fact extraction.
- **📅 Automated Scheduler:** Docker-ready logic in `orchestrator/` that refreshes the knowledge base daily at 09:30 AM IST.

---

## 🚀 Local Setup Guide

Follow these steps to get `groww-factor` running on your local machine.

### 1. Clone & Dependencies
```bash
git clone https://github.com/puneet225/Milestone_1.git
cd Milestone_1
python -m venv .venv
source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file and add your Google API Key:
```bash
cp .env.example .env
# Open .env and set GOOGLE_API_KEY=your_key_here
```

### 3. Initialize Ingestion (First Run)
Manually trigger the pipeline to build your local ChromaDB vector store:
```bash
python orchestrator/run_pipeline.py --force
```

### 4. Run Application
You can run the full stack using Docker (easiest) or manually.

#### Option A: Docker Compose (Recommended)
```bash
docker compose up --build
```

#### Option B: Manual (Development)
**Start Backend:**
```bash
# In one terminal
python orchestrator/scheduler.py  # Starts API + Background Scheduler
```
**Start Frontend:**
```bash
# In another terminal
cd frontend_next_js
npm install
npm run dev
```

---

## 🛠️ Technology Stack

| Component | Choice |
|---|---|
| **Frontend** | [Next.js](https://nextjs.org/) (React, TypeScript) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| **AI Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) |
| **Vector Database** | [ChromaDB](https://docs.trychroma.com/) |
| **LLM** | [Google Gemini](https://ai.google.dev/) (Flash 1.5 Latest & text-embedding-004) |
| **Deployment** | [Vercel](https://vercel.com/) (Frontend) & [Render](https://render.com/) (Backend) |

---

## 🔗 Documentation

- [🏗️ Detailed Architecture](ARCHITECTURE.md)
- [📖 API Reference](API_DOCUMENTATION.md)
- [☁️ Deployment Guide (Render/Vercel)](DEPLOYMENT_GUIDE.md)

---

## 📜 Disclaimer
*groww-factor provides factual data sourced directly from AMC portals. It is not an investment advisory platform. Investing in Mutual Funds is subject to market risks.*
