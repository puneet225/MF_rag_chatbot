# System Architecture: The Pinpoint RAG Pipeline 📐

Groww-Factor is built on a **High-Density Synchronous Pipeline** designed to ensure that the AI's "internal truth" is 100% aligned with the latest fund data.

## 1. Unified Ingestion Pipeline (The Orchestrator)
The Orchestrator is the heart of the "Digital Mirror." It performs three critical steps:
- **Recursive Scraping**: Uses high-fidelity HTTPX mimicry to extract `__NEXT_DATA__` from official fund URLs.
- **Master Merge**: Combines pricing (NAV), stats (AUM), and compliance (Tax) folders into a single factual state.
- **Natural Language Translation**: Translates raw data into pinpoint-accurate sentences:
  > *"The latest NAV for HDFC Mid Cap is Rs 221.614..."*

## 2. Intent-Aware Retrieval
Our RAG system doesn't just "search" for keywords; it classifies the user's intent to ensure the most relevant "Golden Facts" are pulled first:
- **Classifier**: Detects if the query is about NAV, AUM, Taxation, or General Fund Info.
- **Retriever**: Uses a **ChromaDB** vector store with specialized embeddings to find the exact Natural Language Sentence required.

## 3. The LangGraph Controller
The conversation flow is managed by a state-aware graph, ensuring every answer is validated before being delivered:
- **Node A (Retrieve)**: Pulls the "Digital Mirror" facts.
- **Node B (Generate)**: A strictly minimalist generator that mirrors the source without adding "fluff."
- **Node C (Validate)**: Ensures the response contains no investment advice and no hallucinations.

## 4. Production Stability
- **Ephemeral Sync**: On Render, the system utilizes a GitHub Action to trigger a full re-ingestion every 24 hours, ensuring the database is always current.
- **Frontend Proxy**: Next.js proxies API calls to the Render backend, securing the communication channel.

---
*Developed for Milestone 1 by Puneet Mall.*
