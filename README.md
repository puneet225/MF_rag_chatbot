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

### 1. The Ingestion Pipeline (Phase 4)
The system scrapes and indexes data from curated fund sources daily using a 7-stage pipeline.

```mermaid
graph LR
    A[URL Registry] --> B[Playwright Scraper]
    B --> C[Content Normalizer]
    C --> D[Quality Filter]
    D --> E[Gemini Embedding]
    E --> F[(ChromaDB)]
    subgraph "Internal Safety"
    D -.->|Keyword Check| D
    end
```

### 2. The Query Logic (LangGraph)
We use a 6-node state machine to ensure deterministic routing and safety.

```mermaid
graph TD
    User([User Query]) --> Intent[Intent Classifier]
    Intent --> Safety{PII Guard}
    
    Safety -->|PII Detected| Block[Privacy Refusal]
    Safety -->|No PII| Route{Router}
    
    Route -->|Greeting| Greet[Hello Node]
    Route -->|Advisory| Refuse[Advisory Refusal]
    Route -->|Factual| RAG[Hybrid Retrieval]
    
    RAG --> Gen[Gemini Generation]
    Gen --> Post[Post-Validation]
    Post --> Display([User Response])
    
    Block --> Display
    Greet --> Display
    Refuse --> Display
```

---

## 🔒 Key Features

- **🛡️ PII Firewall:** Standalone regex-driven guard catching PAN, Aadhaar, Emails, and Bank details before they hit the LLM.
- **⚖️ Compliance Post-Check:** Every response is validated against 10+ forbidden advisory patterns (e.g., "I recommend", "buy", "better than").
- **⚡ Hybrid Retrieval:** 60% Dense Vector / 40% BM25 Keyword search for precise numerical fact extraction.
- **📅 Automated Scheduler:** Docker-ready service that refreshes the knowledge base daily at 09:30 AM IST.

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

## 🔗 Documentation

- [📖 API Reference](API_DOCUMENTATION.md)
- [☁️ Deployment Guide (Render/Vercel)](DEPLOYMENT_GUIDE.md)
- [🏗️ Detailed Architecture](Docs/rag-architecture.md)

---

## 📜 Disclaimer
*groww-factor provides factual data sourced directly from AMC portals. It is not an investment advisory platform. Investing in Mutual Funds is subject to market risks.*
