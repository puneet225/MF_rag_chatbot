# RAG Architecture: HDFC Mutual Fund FAQ Assistant

This document describes the complete retrieval-augmented generation (RAG) architecture for the facts-only mutual fund FAQ assistant defined in `Problem_statement.md`. It prioritises accuracy, provenance, and regulatory compliance over open-ended conversational ability.

---

## 1. Design Principles

| Principle | Implication for architecture |
|---|---|
| **Facts-only** | Retrieval gates what the model may say; system prompts and post-checks forbid advice and comparisons. |
| **Single canonical source per answer** | Retrieval returns chunks tagged with one citation URL; generation is constrained to cite that URL only. |
| **Curated corpus** | Ingestion is batch or Docker-scheduled from an allowlist of URLs; no arbitrary web crawling at query time. |
| **No PII** | No user document upload path; regex-based PII guards (PAN, Aadhaar) block processing before retrieval; chat payloads exclude identifiers. |
| **Accuracy over "intelligence"** | Prefer abstention ("I couldn't find this in the indexed sources") or refusal over speculative answers. |
| **Separation of concerns** | Offline ingestion pipeline and online query API are distinct Docker services sharing only a persistent ChromaDB volume. |

---

## 2. Components in Brief

| Component | Responsibility |
|---|---|
| **Docker Compose Orchestrator** | Runs two services (`api`, `ingestion`) sharing a named volume `chroma_data` mapped to `/app/chroma_db`. See §4.0. |
| **Ingestion Worker (Docker service)** | On startup (or on schedule), reads the URL allowlist, fetches every page via `AsyncHtmlLoader` + Playwright, normalises → chunks → embeds (Gemini Embedding) → upserts into ChromaDB. |
| **ChromaDB (Shared Volume)** | On-disk PersistentClient at `/app/chroma_db`, collection `hdfc_funds`. Written by the ingestion worker, read by the API at query time. |
| **FastAPI Backend (Docker service)** | Exposes `POST /chat`, `GET /health`. Receives user message + `thread_id`, invokes the LangGraph state machine, returns `{ response, intent, citation }`. |
| **LangGraph State Machine** | Six-node directed graph: `classify_intent → safety_guard → [greeting | refusal | retrieval → generation]`. Compiled with `MemorySaver` checkpointer for per-thread persistence. |
| **Query Router (Intent Classifier)** | Gemini Flash zero-shot classification into `factual`, `advisory`, `greeting`, or `privacy_risk` before any retrieval occurs. |
| **Hybrid Retriever** | `EnsembleRetriever` (60% dense vector / 40% BM25 keyword) pulling top-k=3 chunks per method from ChromaDB. |
| **Generation Node** | Gemini Flash with strict system prompt: ≤ 3 sentences, facts-only, no advice, exactly one citation URL + `Last updated from sources: <date>` footer. |
| **Safety & Refusal Layer** | Regex PII detection (PAN/Aadhaar) in `safety_guard_node`; templated polite refusal with AMFI educational link for advisory queries. |
| **Next.js Frontend** | `frontend_next_js/` — React SPA with dark mode toggle, Groww-inspired UI (`#00D09C`), glassmorphism, starter question chips. Communicates with FastAPI via `fetch()` to `POST /chat`. |

---

## 3. Corpus & Data Model

### 3.1 Scope (current corpus)

**AMC:** HDFC Mutual Fund.
**Source type:** Groww scheme page HTML (no PDFs in this phase).
**Allowlisted URLs:**

| Scheme | URL |
|---|---|
| HDFC Mid Cap Opportunities Fund | `https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth` |
| HDFC Flexi Cap Fund (Equity Fund) | `https://groww.in/mutual-funds/hdfc-flexi-cap-fund-direct-growth` |
| HDFC Focused 30 Fund | `https://groww.in/mutual-funds/hdfc-focused-30-fund-direct-growth` |
| HDFC ELSS Tax Saver Fund | `https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth` |
| HDFC Top 100 Fund (Large Cap) | `https://groww.in/mutual-funds/hdfc-top-100-fund-direct-growth` |

**Out of scope for now:** AMC PDFs (KIM, SID), standalone factsheet PDFs, AMFI/SEBI pages, and additional URLs. The ingestion pipeline should be built so PDFs and extra allowlist entries can be added later without redesign.

**Note:** The problem statement targets official AMC / AMFI / SEBI sources. This phase uses Groww pages as the curated HTML corpus; expanding to primary documents is a future corpus upgrade.

### 3.2 Document metadata (per chunk)

Store at minimum:

| Field | Purpose |
|---|---|
| `source` | Canonical page URL, used as the citation link (exactly one per assistant message). |
| `source_type` | Currently `official_groww_page`; later `factsheet`, `kim`, `sid`, `amfi`, `sebi` as corpus expands. |
| `scheme_name` | Scheme name derived from URL slug (e.g., "Hdfc Mid Cap Fund Direct Growth"). |
| `asset_management_company` | AMC identifier, currently always `HDFC Mutual Fund`. |
| `last_updated` | ISO date of scrape run (populates the `Last updated from sources:` footer). |
| `content_hash` | *(Planned)* Detect content drift on re-crawl; skip re-embedding when unchanged. |

### 3.3 Chunking strategy

**HTML (Groww scheme pages):**
- **Current implementation:** `RecursiveCharacterTextSplitter` with `chunk_size=800`, `chunk_overlap=100`, separators `["\n\n", "\n", ". ", " ", ""]`.
- **Rationale:** 800 characters (~200 tokens) with 100-character overlap ensures table rows and section boundaries remain intact for financial data like expense ratio / exit load / SIP minimums.
- **Pre-processing:** `Html2TextTransformer` converts raw HTML to plain text. `clean_and_tag_documents()` strips empty lines and attaches metadata (§3.2).

**PDF:** Not used in the initial corpus; when added later, use page- or section-aware chunking and avoid splitting mid-table when detectable.

**De-duplication:** *(Planned)* Same URL + overlapping `content_hash` → keep one primary chunk or merge metadata.

---

## 4. Ingestion Pipeline (Detailed)

### 4.0 Scheduler & Infrastructure — Docker Compose

**Product default:** The ingestion service runs a lightweight Python scheduler natively inside its Docker container (`scheduled_ingestion.py`). It executes an initial pipeline run immediately on startup, writes an `initial_boot_complete.flag`, and then enters an idle wait state, executing daily at **09:30 AM (Asia/Kolkata)**.

**Implementation:** `docker-compose.yml` at the project root defines:

| Service | Image | Purpose | Exposed Ports |
|---|---|---|---|
| `api` | `Dockerfile` (Python 3.11 + Playwright) | FastAPI backend serving LangGraph queries | `8001:8001` |
| `ingestion` | Same `Dockerfile` | Runs `scheduled_ingestion.py` daily | None |

**Shared State:** Both services mount a Docker named volume `chroma_data` to `/app/chroma_db` and `manifests_data` to `/app/data/manifests`.
**Synchronisation:** The `api` container relies on `depends_on: condition: service_healthy` for the `ingestion` service, strictly waiting until `initial_boot_complete.flag` physically exists before booting.

**Secrets:** `GOOGLE_API_KEY` is loaded from `.env` mounted into both containers (`./.env:/app/.env`). Never commit `.env` with production keys.

**Dockerfile details:**
- Base: `python:3.11-slim`.
- System deps: `build-essential`, `gcc`, `libffi-dev`, `curl` (for compilation and Playwright).
- `playwright install --with-deps chromium` for `AsyncHtmlLoader`.
- Copies `requirements.txt`, installs, copies application code.
- Default CMD: `uvicorn main:app --host 0.0.0.0 --port 8001` (overridden by `ingestion` service).

**Idempotency:** Ingestion may be re-run safely. `Chroma.from_documents()` currently replaces the collection contents on each run. A future `content_hash`-based upsert would avoid redundant embedding calls.

**Manual runs:** Without Docker, the ingestion script can be executed directly: `python scripts/ingest_data.py` from the project root.

### 4.1 Stages

| Stage | Implementation | Details |
|---|---|---|
| **URL registry** | Hardcoded list `URLS` in `scripts/ingest_data.py` | 5 Groww scheme page URLs. Extend by appending to this list. |
| **Fetch (scraping)** | `AsyncHtmlLoader(URLS)` from `langchain_community` | Uses Playwright under the hood for JS-rendered pages. Respect robots.txt manually (no built-in enforcement). |
| **Normalise** | `Html2TextTransformer` + `clean_and_tag_documents()` | Strips HTML to plain text, removes empty lines, enriches with scheme name / AMC / date metadata. |
| **Chunk** | `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)` | Separators: `["\n\n", "\n", ". ", " ", ""]`. |
| **Embed** | `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")` | Google Gemini embedding model; requires `GOOGLE_API_KEY`. |
| **Index** | `Chroma.from_documents(persist_directory="./chroma_db", collection_name="hdfc_funds")` | Local PersistentClient; persists to disk at `./chroma_db` (mapped to Docker volume in containerised mode). |

### 4.2 Failure handling

| Failure Mode | Current Behaviour | Recommended Improvement |
|---|---|---|
| Non-2xx response / timeout from Groww | `AsyncHtmlLoader` raises exception; `try/except` logs and returns early, **aborting entire run**. | Catch per-URL; log, skip failed URL, continue with remaining. |
| Empty or garbage HTML parse | No detection; garbage text is chunked and embedded silently. | Add content quality heuristic (min character count, required keywords like "NAV" or "Expense Ratio"); flag or exclude low-confidence chunks. |
| Chroma write failure | Exception logged; no retry. | Retry once; alert operator. |
| API key missing | Early return with log message; no data written. | *(Adequate for now.)* |

### 4.3 Structured fund metrics *(Planned)*

For fields like NAV, minimum SIP, expense ratio, rating — dense retrieval alone can return the wrong span or a stale phrasing. A hybrid approach is recommended:

| Layer | What it stores | Role |
|---|---|---|
| **Structured "facts" store** (JSON per scheme per scrape run) | Typed fields: `nav`, `minimum_sip`, `expense_ratio`, `fund_size`, `rating` | Exact answers, filters, regression tests |
| **Vector index (chunks)** | Full normalised text from the same page | Narrative context, exit load, benchmark, objectives |

**Not yet implemented.** When added, the retrieval node can short-circuit chunk search for column-mapped questions ("What is the minimum SIP?") and answer from the structured row (still citing `source_url`).

---

## 5. Runtime Query Pipeline — LangGraph State Machine

**Implementation:** `core/graph.py`, `core/nodes.py`, `core/state.py`, `core/retriever.py`.
**Orchestration:** LangGraph `StateGraph` compiled with `MemorySaver` checkpointer for per-thread conversation persistence.

### 5.0 State schema (`core/state.py`)

```
ChatState (TypedDict):
  messages:           Annotated[List[BaseMessage], add_messages]  # Full conversation history per thread
  intent:             str          # "factual" | "advisory" | "greeting" | "privacy_risk"
  retrieved_docs:     List[dict]   # Chunk dicts from ChromaDB
  identified_scheme:  str          # Scheme name if resolved (currently unused by nodes)
  response:           str          # Final assistant response text
  citation:           str          # Single source URL for the footer
```

### 5.1 Graph topology

```
START → classify_intent → safety_guard → [conditional routing]
                                              │
                           ┌──────────────────┼──────────────────┐
                           ▼                  ▼                  ▼
                    privacy_risk → END   greeting → END   advisory → refusal → END
                                                                 │
                                                          factual (default)
                                                                 ▼
                                                           retrieval → generation → END
```

**Routing logic (`route_after_safety`):**
- `privacy_risk` → `END` (response already set by safety_guard).
- `greeting` → `greeting` node → `END`.
- `advisory` → `refusal` node → `END`.
- Everything else → `retrieval` → `generation` → `END`.

### 5.2 Node details

#### Node 1: `classify_intent_node`
- **Model:** `gemini-3.1-flash-lite-preview`, temperature 0.
- **Prompt:** System prompt instructs zero-shot classification into `factual`, `advisory`, `greeting`, or `privacy_risk`.
- **Output:** Sets `state.intent` to the lowercase category string.
- **Edge case:** Compound queries ("What is the expense ratio, and should I invest?") — the classifier may return `factual`, bypassing the advisory refusal. *(See Edge_Cases.md §3.)*

#### Node 2: `safety_guard_node`
- **Mechanism:** Regex-based PII detection, not LLM-based.
  - PAN pattern: `[A-Z]{5}[0-9]{4}[A-Z]{1}`
  - Aadhaar pattern: `[2-9]{1}[0-9]{3}\s[0-9]{4}\s[0-9]{4}` or 12-digit continuous.
- **On match:** Overrides `state.intent` to `privacy_risk` and sets a templated refusal response.
- **On no match:** Passes state through unchanged.
- **Limitation:** Only catches PAN/Aadhaar; does not detect email, phone, or account numbers. *(See Edge_Cases.md §2.)*

#### Node 3: `refusal_node`
- **Trigger:** `intent == "advisory"`.
- **Response:** Static templated message: *"I am a facts-only assistant and cannot provide investment advice…"*
- **Citation:** `https://www.amfiindia.com/investor-corner` (AMFI educational portal).
- **No retrieval or LLM call occurs.**

#### Node 4: `greeting_node`
- **Trigger:** `intent == "greeting"`.
- **Response:** Static welcome message listing capabilities (expense ratios, exit loads, SIP amounts).
- **No retrieval or LLM call occurs.**

#### Node 5: `retrieval_node`
- **Trigger:** `intent == "factual"` (default route).
- **Implementation:** Calls `core.retriever.get_retriever()` which builds an `EnsembleRetriever`. See §5.3.
- **Output:** Sets `state.retrieved_docs` (list of chunk dicts) and `state.citation` (first retrieved doc's `source` URL).

#### Node 6: `generation_node`
- **Trigger:** Always follows `retrieval_node`.
- **Model:** `gemini-3.1-flash-lite-preview`, temperature 0.
- **System prompt:** Strict constraints — use ONLY provided CONTEXT, max 3 sentences, no investment advice, no opinions, say "I don't know" if context is insufficient.
- **Context packaging:** All retrieved chunk texts concatenated with `\n\n` separators, injected into the system prompt's `CONTEXT` block.
- **Output format:** `{response_text}\n\n**Source:** {citation_url}\n*Last updated from sources: {last_updated_date}*`
- **Fallback:** If `retrieved_docs` is empty, returns a static "could not find information" message without calling the LLM.

### 5.3 Retrieval layer (`core/retriever.py`)

**Strategy:** Hybrid retrieval via `EnsembleRetriever`.

| Retriever | Weight | Top-k | Source |
|---|---|---|---|
| **Dense (Vector)** | 0.6 | 3 | ChromaDB `hdfc_funds` collection, Gemini Embedding cosine similarity |
| **Keyword (BM25)** | 0.4 | 3 | `BM25Retriever` initialised from all ChromaDB documents at query time |

**Embedding model:** `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")` — same model at index build and query time.

**ChromaDB connection:** `Chroma(persist_directory="./chroma_db", collection_name="hdfc_funds")`. In Docker, `./chroma_db` resolves to `/app/chroma_db` on the shared volume.

**BM25 initialisation:** Currently reads all documents from ChromaDB on every query (`vectorstore.get()`) to build the BM25 index. This is acceptable for a small corpus (~500 chunks) but should be cached for scale.

**Source selection for "exactly one link":** The first retrieved document's `source` metadata field is used as the citation URL. No conflict resolution across multiple source URLs.

---

## 6. Generation Layer Constraints

### 6.1 Output contract (per `Problem_statement.md`)

| Field | Rule |
|---|---|
| **Body** | ≤ 3 sentences, factual, no "you should invest". |
| **Citation** | Exactly one URL, matching the retrieved chunk's `source` metadata. |
| **Footer** | `Last updated from sources: <date>` using the chunk's `last_updated` metadata. |

### 6.2 Model choice

| Role | Model | Provider | Temperature |
|---|---|---|---|
| Intent classification | `gemini-3.1-flash-lite-preview` | Google AI (via `GOOGLE_API_KEY`) | 0 |
| Answer generation | `gemini-3.1-flash-lite-preview` | Google AI (via `GOOGLE_API_KEY`) | 0 |
| Embedding (index + query) | `models/gemini-embedding-001` | Google AI (via `GOOGLE_API_KEY`) | N/A |

**Single API key** (`GOOGLE_API_KEY`) covers all three roles.

### 6.3 Post-generation validation *(Planned — not yet implemented)*

Programmatic checks to run after generation, before returning to the user:

| Check | Rule | On failure |
|---|---|---|
| Sentence count | ≤ 3 (heuristic: `. ? !` count) | Regenerate once with stricter prompt, or truncate. |
| Citation URL present | Exactly one HTTP(S) URL in response, and it matches an allowlisted URL | Inject correct URL from `state.citation`. |
| Forbidden patterns | Regex for: "invest in", "you should", "better than", "outperform", "guarantee", "recommend" | Regenerate once, or fall back to templated safe response. |

---

## 7. Refusal & Safety Layer

### 7.1 Advisory / comparative queries

- **Router:** `classify_intent_node` uses Gemini zero-shot to detect advisory intent.
- **Detection targets:** "should I", "which is better", "best fund", "recommend", implicit ranking, personal situation ("I am 45…").
- **Action:** No retrieval occurs. Static refusal response + AMFI educational link.

### 7.2 Privacy guard

- **Mechanism:** Regex in `safety_guard_node` (runs after intent classification, before routing).
- **Patterns:** PAN (`[A-Z]{5}[0-9]{4}[A-Z]{1}`), Aadhaar (12-digit or 4-4-4 format).
- **On detection:** Overrides intent to `privacy_risk`, sets a security-focused refusal message, route goes directly to `END`.
- **Gap:** Does not yet detect email addresses, phone numbers, or bank account numbers. *(See Edge_Cases.md §2.)*

### 7.3 Privacy policy

Per `Problem_statement.md`, the system must not request, store, or process: PAN, Aadhaar, account numbers, OTPs, email addresses, or phone numbers. If the UI ever supports "paste your statement text" — that is out of scope for this product and must not be implemented unless requirements change.

---

## 8. Multi-Thread Chat Architecture

### 8.1 Thread model

- **Thread ID:** Opaque string identifier per conversation (default `"default_user"`, overridden by frontend with UUID).
- **Persistence:** `MemorySaver` checkpointer (in-memory); conversation state is per-`thread_id`, includes full `messages` list.
- **Isolation:** Switching `thread_id` loads a completely independent state. No cross-thread data bleed.

### 8.2 Context window policy

- **Current:** Full thread message history is sent to LangGraph on every invocation via the `messages` state key with `add_messages` reducer.
- **Risk:** Long-lived threads will accumulate unbounded history, increasing Gemini API token costs and latency. *(See Edge_Cases.md §5.)*
- **Recommended:** Implement a sliding window (last N turns, e.g. 4–6) for the LLM context while retaining full history in the checkpointer for UI rendering.

### 8.3 Concurrency

- Stateless FastAPI server; thread state in `MemorySaver` (in-process dict).
- Vector store is read-only at query time; no cross-thread writes.
- **Production consideration:** Replace `MemorySaver` with a durable store (SQLite, Postgres, Redis) for multi-process / multi-container deployments where in-memory state would be lost on restart.

---

## 9. Application & API Layer

### 9.1 Endpoints

**Implementation:** `main.py` — FastAPI application.

| Endpoint | Method | Purpose |
|---|---|---|
| `/chat` | `POST` | User message → LangGraph pipeline → assistant message. Accepts `{ message, thread_id? }`, returns `{ response, intent, citation? }`. |
| `/health` | `GET` | Liveness probe. Returns `{ status: "ok" }`. |

**CORS:** `CORSMiddleware` with `allow_origins=["*"]` to permit requests from the Next.js frontend (any port).

### 9.2 Request / Response schemas

```
ChatRequest:
  message:    str           # User's question
  thread_id:  Optional[str] # Defaults to "default_user"

ChatResponse:
  response:   str           # Full assistant reply including citation footer
  intent:     str           # "factual" | "advisory" | "greeting" | "privacy_risk"
  citation:   Optional[str] # Source URL
```

### 9.3 Frontend (Next.js)

**Location:** `frontend_next_js/` — `create-next-app` React SPA.
**Components:** `ThemeProvider.tsx` (dark mode context), `page.tsx` (main chat UI).
**Features:** Groww-inspired colour palette (`#00D09C`), glassmorphism, dark mode toggle, starter question chips, disclaimer banner ("Facts-only. No investment advice.").
**Communication:** Direct `fetch("http://localhost:8001/chat", { method: "POST", body: JSON.stringify({ message, thread_id }) })`.

---

## 10. Observability & Quality *(Planned)*

### 10.1 Logging

- `print()` statements in `main.py` and nodes for request lifecycle tracing.
- `logging` module in `scripts/ingest_data.py` with `INFO` level for ingestion phases.
- **Recommended:** Structured logging (JSON) with request ID correlation, query latency, retrieval count, router decision, refusal vs answer classification.

### 10.2 Evaluation (offline)

- **Golden set:** ~50–100 Q&A pairs from the corpus with expected source URL and allowed answer variants.
- **Metrics:** Citation URL exact match rate, grounding (answer supported by chunk), refusal precision/recall on advisory prompts.
- **Existing test:** `tests/test_retriever.py` — smoke test querying "What is the expense ratio of HDFC Mid Cap?" and printing the first retrieved chunk.

### 10.3 Drift detection

- *(Planned)* Re-crawl alerts when `content_hash` changes for critical allowlisted URLs.
- Currently no content hashing or diff detection between ingestion runs.

---

## 11. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| **Infrastructure** | Docker Compose (`Dockerfile` + `docker-compose.yml`) | Two services: `api` + `ingestion`, shared `chroma_data` volume. |
| **Ingestion scheduler** | Docker service (run-once or loop-based) | Extensible to cron or orchestrator. |
| **Vector DB** | ChromaDB — `PersistentClient` on disk at `./chroma_db` | Collection: `hdfc_funds`. Same path at ingest and query time. |
| **Embeddings** | Google Gemini `models/gemini-embedding-001` via `langchain-google-genai` | Requires `GOOGLE_API_KEY`. |
| **LLM** | Google Gemini `gemini-3.1-flash-lite-preview` via `langchain-google-genai` | Temperature 0, single API key for both classification and generation. |
| **Orchestration** | LangGraph `StateGraph` with `MemorySaver` checkpointer | Six-node directed graph with conditional routing. |
| **Keyword retrieval** | BM25 via `rank_bm25` / `langchain_community.retrievers.BM25Retriever` | Ensembled with vector retrieval (40/60 weight). |
| **Web framework** | FastAPI + Uvicorn | Port 8001, CORS enabled. |
| **Frontend** | Next.js (React, TypeScript, `create-next-app`) | Groww-inspired theming, dark mode, glassmorphism. |
| **Scraping** | Playwright + `AsyncHtmlLoader` + `Html2TextTransformer` | JS-rendered page support. |
| **Environment** | `python-dotenv` for `.env` loading | `GOOGLE_API_KEY` is the only required secret. |

**Frozen parameters (must match across ingest and query):**
- Embedding model: `models/gemini-embedding-001`
- ChromaDB collection: `hdfc_funds`
- Persist directory: `./chroma_db` (or `/app/chroma_db` in Docker)

---

## 12. Known Limitations (Architectural)

| Limitation | Impact | Mitigation |
|---|---|---|
| **Stale data** | Answers reflect last ingestion run; financial fields (NAV, AUM) change daily. | Footer date communicates staleness; schedule frequent re-ingestion. |
| **HTML layout variance** | If Groww changes page structure, `Html2TextTransformer` may extract noise or miss data. | Content quality heuristics on ingest; alerting on `content_hash` drift. |
| **Narrow corpus** | Only 5 indexed scheme pages are answerable; broad MF questions get a weak "can't find" response. | Expand URL allowlist; add AMFI/SEBI pages; future PDF ingestion. |
| **Router mistakes** | Misclassified advisory queries leak through to generation. | Combine router + post-generation forbidden-pattern checks (§6.3). |
| **No real-time market data** | By design — this is a documentation-backed FAQ, not a trading terminal. | Explicit in disclaimer. |
| **BM25 index rebuilt per query** | Small performance hit per request (all docs fetched from Chroma to build BM25). | Cache BM25 index; rebuild only on ingest. |
| **MemorySaver is in-memory only** | Thread state lost on container restart; does not scale to multi-process. | Migrate to SQLite or Postgres checkpointer for production. |
| **No post-generation validation** | Model could exceed 3 sentences, omit citation, or include soft advice. | Implement §6.3 programmatic checks. |
| **PII detection is regex-only** | Misses emails, phone numbers, account numbers. | Expand regex patterns; optional NLP-based PII entity detection. |
| **Unbounded context window** | Long threads accumulate full message history, inflating token costs. | Implement sliding window (last 4–6 turns) for LLM context. |

For a comprehensive list of edge-case failure scenarios, see `Edge_Cases.md`.

---

## 13. Alignment with Deliverables

| Deliverable (from `Problem_statement.md`) | Where it lives |
|---|---|
| README: setup, AMC/schemes, architecture, limitations | This file + `README.md` + `Problem_statement.md` + `Edge_Cases.md`. |
| Disclaimer snippet ("Facts-only. No investment advice.") | Next.js UI banner + `refusal_node` response text + generation system prompt. |
| Multi-thread chat | §8: `MemorySaver` checkpointer keyed by `thread_id`; API accepts `thread_id` per request. |
| Facts-only + one citation + footer | §5.2 (generation node) + §6.1 (output contract): system prompt enforces ≤ 3 sentences, single URL, dated footer. |
| Refusal of advisory queries | §7.1: intent classifier + `refusal_node` with AMFI educational link. |
| Privacy (no PII) | §7.2: regex PII guard in `safety_guard_node`; no upload path; no PII in logs. |

---

## 14. Summary

The architecture is a **closed-book RAG system**: a curated, versioned corpus of 5 allowlisted Groww HDFC scheme page URLs is refreshed by a **Docker-based ingestion worker** that runs `scrape → normalise → chunk (800 chars / 100 overlap) → embed (Gemini Embedding) → upsert (ChromaDB on shared Docker volume)`; at query time, a **LangGraph state machine** routes through intent classification (Gemini Flash) → PII regex guard → hybrid retrieval (60% vector + 40% BM25, top-3 each) → constrained generation (Gemini Flash, ≤ 3 sentences, one citation, dated footer) — with hard refusal paths for advisory, comparative, and privacy-violating requests. Multi-thread support is handled by `MemorySaver` per-`thread_id` checkpointing, and the entire stack is orchestrated via `docker-compose up --build`.
