# Edge Cases & Failure Scenarios

This document outlines scenarios and edge cases that the current architecture and implementation of the HDFC Mutual Fund FAQ Assistant may struggle to handle or fail completely. These are based on the system constraints defined in the `Problem_statement.md` and the architecture in `rag-architecture.md`.

## 1. Data Ingestion & Source Reliability
*   **Target Website Structural Changes (DOM changes):** The ingestion pipeline relies on Playwright to scrape HTML from Groww. If Groww updates their DOM structure, class names, or obfuscates data, the `Html2TextTransformer` might extract unstructured noise, leading to garbage data in ChromaDB.
*   **Dead Links (404s):** The HDFC scheme URLs are hardcoded in `ingest_data.py`. If Groww changes a URL slug natively, the scraper will ingest a 404 page into the vector database, silently corrupting the knowledge base.
*   **Database Locking during Re-ingestion:** If the offline `ingest_data.py` script attempts to write to ChromaDB at the exact same moment the FastAPI backend is reading from it for a user query, it could result in SQLite `database is locked` errors, crashing the API request.

## 2. PII Collection Violations
*   **Accidental PII in Prompts:** The constraints explicitly forbid processing PAN, Aadhaar, or Account numbers. However, if a user inputs their query as `"My PAN is ABCDE1234F, what is the exit load for HDFC Flexi Cap?"`, the system currently has no pre-processing firewall. It will send the PII to Gemini and persist it in the LangGraph memory state (`thread_id`), violating the constraint.

## 3. Strict "Facts-Only" & Constraints Adherence
*   **Compound "Sneaky" Queries:** A query like *"What is the expense ratio of HDFC Mid Cap and HDFC Flexi Cap, and which is better?"* might pass the Intent Node because it contains factual requests, but the Generation node might violate the "no comparisons" rule while attempting to answer all parts of the prompt in under 3 sentences.
*   **Information Void (Missing Facts):** If a user asks a highly specific technical fact that is simply not present on the Groww landing page (e.g., obscure NRI tax implications), the Retriever might fetch the closest semantic match, causing the Generation Node to potentially hallucinate or force-fit an irrelevant answer instead of aggressively stating "I don't know."

## 4. Ambiguity and Entity Confusion
*   **Vague Fund References:** If a user asks *"What is the NAV of the equity fund?"* without specifying which of the 5 schemes they mean, the BM25 and Vector search engines might pull chunks from all 5 funds. The Generation node might merge the NAVs into a single confused response or exceed the 3-sentence constraint trying to list them all.

## 5. System Limits & Abuse
*   **Rate Limiting & Quota Exhaustion:** The FastAPI layer lacks IP or token-based rate limiting. A single malicious user (or script) could spam the `/chat` endpoint, rapidly depleting the Google Gemini API quota or causing a Denial of Service (DoS).
*   **Context Window Bloat:** Because LangGraph maintains session state via `thread_id`, a user who stays in the same session and has a 500-turn long conversation will eventually see the system send an enormous chat history to the Intent/Generation nodes, blowing up API costs and increasing latency significantly.

## 6. Edge Case User Behaviors
*   **Multilingual Queries:** If a user asks *"HDFC Mid cap ka minimum SIP kitna hai?"* (Hindi), Gemini will understand it, but without explicit systemic instructions, it may respond inconsistently in Hindi without the enforced English citation footers, breaking the strict UI formatting.
