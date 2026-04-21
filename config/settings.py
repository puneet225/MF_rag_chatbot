"""
Centralised settings for the RAG Mutual Fund FAQ Assistant.

All tuneable parameters and environment-variable overrides live here.
Import from `config.settings` throughout the project instead of scattering
os.getenv() calls or magic numbers across modules.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ────────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ─── Model Configuration ─────────────────────────────────────────────────────
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3-flash-preview")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
LLM_TEMPERATURE = 0  # Deterministic for facts-only responses

# ─── ChromaDB ─────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "hdfc_funds")

# ─── Retrieval ────────────────────────────────────────────────────────────────
VECTOR_SEARCH_K = int(os.getenv("VECTOR_SEARCH_K", "3"))
BM25_SEARCH_K = int(os.getenv("BM25_SEARCH_K", "3"))
VECTOR_WEIGHT = 0.6
BM25_WEIGHT = 0.4

# ─── Ingestion ────────────────────────────────────────────────────────────────
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))
CHUNK_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
MIN_CONTENT_LENGTH = 500  # Minimum character count for quality filter

# Financial keywords — at least one must be present after HTML→text
# transformation for a document to pass quality validation.
QUALITY_KEYWORDS = [
    "nav", "expense", "sip", "exit load", "aum", "fund size",
    "benchmark", "riskometer", "returns", "portfolio", "holdings"
]

# ─── Generation Constraints ──────────────────────────────────────────────────
MAX_RESPONSE_SENTENCES = 3
CONTEXT_WINDOW_TURNS = 6  # Last N messages sent to LLM for context

# Patterns that must NEVER appear in a generated response
FORBIDDEN_PATTERNS = [
    r"\byou should\b",
    r"\binvest in\b",
    r"\bbetter than\b",
    r"\bworst\b",
    r"\boutperform\b",
    r"\bguarantee\b",
    r"\brecommend\b",
    r"\bI suggest\b",
    r"\bbuy\b",
    r"\bsell\b",
]

# ─── Paths ────────────────────────────────────────────────────────────────────
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
URL_REGISTRY_PATH = CONFIG_DIR / "url_registry.json"
DATA_DIR = PROJECT_ROOT / "data"
MANIFESTS_DIR = DATA_DIR / "manifests"

# ─── API ──────────────────────────────────────────────────────────────────────
# Render (and many clouds) use the 'PORT' environment variable
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", "8001")))

# ─── Educational / Refusal Links ─────────────────────────────────────────────
AMFI_EDUCATION_URL = "https://www.amfiindia.com/investor-corner"
