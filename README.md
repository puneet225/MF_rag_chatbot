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

## 🛠️ Architecture & Flow

### 1. Data Ingestion & Transformation (Stage: Backend)
The system operates a multi-phase ingestion sequence to transform raw financial data into semantic memory.

```mermaid
flowchart TD
    subgraph Ingestion["Ingestion Pipeline (Daily @ 9:30 AM)"]
        direction TB
        P1[Phase 1: Scraper]
        P2[Phase 2: Normalizer]
        P3[Phase 3: Chunker]
        P4[Phase 4: Vector Store]
        
        P1 -- "Raw HTML" --> P2
        P2 -- "Cleaned Text" --> P3
        P3 -- "Semantic Chunks" --> P4
    end

    subgraph Storage["Permanent Storage"]
        DB[(ChromaDB)]
    end

    P4 -- Update --> DB
```

### 2. Live Runtime & User Interaction
A production-grade microservices flow ensures responsive queries and high security.

```mermaid
flowchart LR
    subgraph Client["Frontend Service (Vercel)"]
        UI[Next.js UI]
    end

    subgraph Server["Backend Service (Render)"]
        direction TB
        API[FastAPI Server]
        Guard{PII Guard}
        LG[LangGraph Logic]
        
        API --> Guard
        Guard --> LG
    end

    subgraph Data["Database"]
        DB[(ChromaDB)]
    end

    User((User)) -- "HTTPS" --> UI
    UI -- "REST API" --> API
    LG -- "Retrieve" --> DB
```

---

## 🔒 Key Features

- **🛡️ PII Firewall:** Standalone regex-driven guard catching PAN, Aadhaar, Emails, and Bank details before they hit the LLM.
- **⚖️ Compliance Post-Check:** Every response is validated against 10+ forbidden advisory patterns (e.g., "I recommend", "buy", "better than").
- **⚡ Hybrid Retrieval:** 60% Dense Vector / 40% BM25 Keyword search for precise numerical fact extraction.
- **📅 Automated Scheduler:** Docker-ready logic in `orchestrator/` that refreshes the knowledge base daily at 09:30 AM IST.

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/puneet225/Milestone_1.git
cd Milestone_1
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Pipeline Manually
If you want to refresh the data immediately:
```bash
python orchestrator/run_pipeline.py --force
```

### 2. Configure
Create a `.env` file from the template:
```bash
cp .env.example .env
# Add your GOOGLE_API_KEY
```

### 3. Run Locally (Docker)
```bash
docker compose up --build
```

---

## 🛠️ Technology Stack

| Component | Choice |
|---|---|
| **Frontend** | [Next.js](https://nextjs.org/) (React, TypeScript) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) (Python) |
| **AI Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) |
| **Vector Database** | [ChromaDB](https://docs.trychroma.com/) |
| **Embeddings & LLM** | [Google Gemini](https://ai.google.dev/) (Flash 1.5 & Embedding-001) |
| **Deployment** | [Vercel](https://vercel.com/) (Frontend) & [Render](https://render.com/) (Backend) |

---

## 🔗 Documentation

- [🏗️ Detailed Architecture](ARCHITECTURE.md)
- [📖 API Reference](API_DOCUMENTATION.md)
- [☁️ Deployment Guide (Render/Vercel)](DEPLOYMENT_GUIDE.md)

---

## 📜 Disclaimer
*groww-factor provides factual data sourced directly from AMC portals. It is not an investment advisory platform. Investing in Mutual Funds is subject to market risks.*
