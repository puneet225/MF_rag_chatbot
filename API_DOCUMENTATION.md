# 📖 groww-factor API Documentation

The `groww-factor` backend is a FastAPI-powered service that orchestrates the LangGraph state machine. It handles intent classification, PII protection, and facts-only RAG generation.

## 📡 Base URLs
- **Local Dev:** `http://localhost:8001`
- **Render Production:** (Your unique Render service URL)

---

## 💬 Chat Endpoint

### `POST /chat`
Submits a user message to the RAG pipeline and retrieves a processed, compliance-verified response.

#### Request Body
```json
{
  "message": "What is the exit load for HDFC Mid Cap?",
  "thread_id": "optional-uuid"
}
```

- `message` (string, required): The user's natural language question.
- `thread_id` (string, optional): A unique ID to maintain conversation history for the session.

#### Response Body (200 OK)
```json
{
    "response": "HDFC Mid Cap Opportunities Fund has an exit load of 1.00% if redeemed within 1 year of allotment. No exit load is charged for redemption after 1 year.",
    "intent": "factual",
    "citation": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth"
}
```

- `response`: The AI-generated, facts-only answer.
- `intent`: One of `factual`, `greeting`, `advisory`, or `privacy_risk`.
- `citation`: The source URL used to ground the answer (if applicable).

#### Error Response (403 Forbidden - PII Detected)
If the `pii_guard` node detects a PAN, Aadhaar, or Bank ID, the API intercepts the request:
```json
{
    "response": "Privacy Warning: I cannot process messages containing personal identity numbers (PAN, Aadhaar) or bank details.",
    "intent": "privacy_risk",
    "citation": null
}
```

---

## 🏥 Health & Maintenance

### `GET /health`
Used by Docker, Render, and Uptime monitors to check if the service is alive.

#### Response
```json
{
  "status": "online",
  "version": "2.1.0"
}
```

---

## ⚙️ Core Configuration (Settings)
The API behavior is controlled via `config/settings.py` using these overrides:
- `LLM_TEMPERATURE`: Fixed at `0` for deterministic factual output.
- `MAX_RESPONSE_SENTENCES`: Caps the AI at 3 sentences to prevent "advice bloat".
- `CONTEXT_WINDOW_TURNS`: Sliding window of last 6 messages to maintain context without token bleed.
