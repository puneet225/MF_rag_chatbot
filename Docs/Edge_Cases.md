# Edge Cases & Failure Scenarios

This document outlines scenarios and edge cases relevant to the HDFC Mutual Fund FAQ Assistant's architecture and constraints. 

Following the implementation of the production-grade architecture (Sprints 1–4), many critical vulnerabilities have been resolved. This document tracks both the **Mitigated Risks** (to prevent regression) and the **Open / Future Risk Areas** (for future hardening).

---

## Part 1: Mitigated Edge Cases (Resolved)

These scenarios have been successfully addressed via systemic guards.

### 1. Data Ingestion Failures 
*   **Dead Links & 404s:** 
    *   *Risk:* A single dead URL or timeout in the source list crashes the entire ingestion run or silently poisons the DB.
    *   *Mitigation:* Pipeline wraps every URL fetch in an isolated `try/except` block. Failed fetch attempts do not disrupt the rest of the ingestion batch; errors are collected and dumped into a permanent `ingest_manifest.json` report.
*   **Database Locking:**
    *   *Risk:* The offline ingestion script attempts to write to ChromaDB at the exact same moment the FastAPI backend reads from it, causing SQLite `database is locked` crashes for end-users.
    *   *Mitigation:* Docker Compose orchestration utilizes `depends_on: service_completed_successfully`. The `api` container physically cannot boot or accept connections until the `ingestion` container finishes its run and exits, ensuring mutually exclusive file handles.

### 2. PII / Constraint Violations
*   **Accidental PII Injection:** 
    *   *Risk:* A user inputs a question embedding PAN, Aadhaar, Email, Phone, or Bank details. The system processes it, saving it to LangGraph history and sending it to Gemini.
    *   *Mitigation:* Standalone, regex-driven `core/pii_guard.py` evaluates all incoming text *before* any intent or LLM routing occurs. If triggered, the pipeline intercepts it into a "privacy risk" branch, halting execution and returning a static refusal without retaining the PII match value.
*   **Compound "Sneaky" Advisory Queries:** 
    *   *Risk:* A query like *"What is the expense ratio of HDFC Mid Cap and HDFC Flexi Cap, and which is better?"* bypasses the zero-shot classifier and forces the generation node to provide investment advice.
    *   *Mitigation:* `core/generator.py` enforces post-generation regex validation blocking strings like `"recommend"`, `"better than"`, and `"buy/sell"`. If triggered, it re-generates against a strict template, or fails safely to a "Please see the URL" fallback.

### 3. System Limits
*   **Context Window Token Bloat:** 
    *   *Risk:* Long-running chat sessions (e.g. 50+ turns) accumulate all messages in LangGraph state, eventually exceeding Gemini's token limits or causing massive latency.
    *   *Mitigation:* `CONTEXT_WINDOW_TURNS = 6` limits the injection of history into the active Generation prompt. Full history is still stored in memory for the UI to display, but the LLM isn't polluted by irrelevant turns.

---

## Part 2: Open / Future Risk Areas (Remaining)

These scenarios remain active edge cases that the current architecture may struggle to handle perfectly.

### 1. Data Ingestion Quality
*   **Target Website Structural Changes (DOM Changes):** 
    *   *Risk:* The ingestion relies on Playwright. If Groww drastically changes its DOM layout or deliberately obfuscates its text, the HTML-to-Text transformer may extract unstructured noise. Even though we have a 500-char/keyword filter, a large blob of noise could still technically pass.
    *   *Impact:* Garbage context retrieved → Hallucinated or broken responses.

### 2. Ambiguity & Entity Confusion
*   **Vague Fund References:** 
    *   *Risk:* A user asks *"What is the NAV of the equity fund?"* without specifying which of the 5 schemes they mean. The vector search will pull chunks spanning all 5 funds based on semantic proximity to "equity".
    *   *Impact:* The generator may synthesize an output merging parameters from different funds, causing a factual collision.

### 3. System Abuse
*   **Rate Limiting & Quota Exhaustion:** 
    *   *Risk:* The FastAPI layer currently operates without Token Bucket or IP-based rate limiting. A single malicious user script spamming the `/chat` endpoint will rapidly deplete the Google AI Studio quota.
    *   *Impact:* Denial of Service (DoS) for all legitimate users once the key is rate-limited by Google.

### 4. Edge Case User Behaviors
*   **Multilingual Factual Queries:** 
    *   *Risk:* A user asks purely factual questions in Hindi ("*HDFC Mid cap ka expense ratio kya hai?*").
    *   *Impact:* Gemini can understand the intent perfectly. However, without explicit systemic instructions mapping translation to output format, it might output a response in a mix of Hindi/English that breaks the strict format required by compliance.

### 5. Numerical / Financial Mathematics
*   **Calculative Queries:**
    *   *Risk:* A user asks: *"If I put ₹10,000 in HDFC Flexi Cap 3 years ago, what is its value today?"* 
    *   *Impact:* The system has facts but no calculator module. The generator might attempt to estimate or hallucinate a compounded return amount based on the retrieved generic past-performance figures, violating the "facts-only / no generation of dates/numbers" constraint. (This is why the future roadmap contains a JSON-backed structured data engine).
