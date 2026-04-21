"""
Phase 4 — Unified Ingestion Pipeline Orchestrator
=================================================

Refactored from scripts/ingest_data.py.
Handles the end-to-end ingestion flow and updates the system state.

New Feature: Writes successful completion timestamp to orchestrator/last_refreshed.txt.
"""

import os
import sys
import json
import hashlib
import datetime
import argparse
import logging
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# ─── Bootstrap ────────────────────────────────────────────────────────────────
# Ensure we are at project root for imports
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import (
    GOOGLE_API_KEY,
    EMBEDDING_MODEL,
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CHUNK_SEPARATORS,
    MIN_CONTENT_LENGTH,
    QUALITY_KEYWORDS,
    URL_REGISTRY_PATH,
    MANIFESTS_DIR,
)

load_dotenv()

# Paths relative to orchestrator/
ORCHESTRATOR_DIR = ROOT_DIR / "orchestrator"
LAST_REFRESHED_PATH = ORCHESTRATOR_DIR / "last_refreshed.txt"

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orchestrator.pipeline")


def update_last_refreshed():
    """Update the last_refreshed.txt file with current UTC timestamp."""
    try:
        ORCHESTRATOR_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        with open(LAST_REFRESHED_PATH, "w") as f:
            f.write(timestamp)
        logger.info(f"Updated cache state: {timestamp}")
    except Exception as e:
        logger.error(f"Failed to update last_refreshed.txt: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. URL Registry Loader
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_url_registry() -> List[Dict[str, str]]:
    if not URL_REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registry missing: {URL_REGISTRY_PATH}")
    with open(URL_REGISTRY_PATH, "r") as f:
        registry = json.load(f)
    logger.info(f"Loaded registry: {len(registry)} schemes")
    return registry


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Fetch
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fetch_urls(registry: List[Dict[str, str]]) -> tuple[List[Document], List[Dict]]:
    url_to_meta = {entry["url"]: entry for entry in registry}
    successful_docs: List[Document] = []
    failures: List[Dict] = []

    for url in url_to_meta.keys():
        try:
            logger.info(f"  Fetching: {url}")
            loader = AsyncHtmlLoader([url])
            docs = loader.load()
            if docs and docs[0].page_content.strip():
                docs[0].metadata["registry"] = url_to_meta[url]
                successful_docs.append(docs[0])
            else:
                failures.append({"url": url, "error": "Empty body"})
        except Exception as e:
            failures.append({"url": url, "error": str(e)})
            logger.error(f"  ✗ Failed: {url}")

    return successful_docs, failures


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Normalise & Clean
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def normalise_documents(docs: List[Document]) -> List[Document]:
    html2text = Html2TextTransformer()
    docs_transformed = html2text.transform_documents(docs)
    current_date = datetime.date.today().strftime("%Y-%m-%d")

    for doc in docs_transformed:
        meta = doc.metadata.pop("registry", {})
        text = "\n".join(l.strip() for l in doc.page_content.split("\n") if l.strip())
        doc.page_content = text
        doc.metadata.update({
            "source": meta.get("url", ""),
            "scheme_name": meta.get("scheme_name", ""),
            "scheme_id": meta.get("scheme_id", ""),
            "amc": meta.get("amc", "HDFC Mutual Fund"),
            "source_type": meta.get("source_type", "official_page"),
            "last_updated": current_date,
        })
    return docs_transformed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Content Quality Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def validate_content_quality(docs: List[Document]) -> tuple[List[Document], List[str]]:
    passed, rejected = [], []
    for doc in docs:
        if len(doc.page_content) < MIN_CONTENT_LENGTH:
            rejected.append(f"Short: {doc.metadata.get('source')}")
            continue
        if not any(kw in doc.page_content.lower() for kw in QUALITY_KEYWORDS):
            rejected.append(f"Non-financial: {doc.metadata.get('source')}")
            continue
        passed.append(doc)
    return passed, rejected


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. Content Hashing / De-duplication
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def filter_unchanged_documents(docs: List[Document], force: bool = False) -> tuple[List[Document], int]:
    hash_path = MANIFESTS_DIR / "content_hashes.json"
    prev_hashes = {}
    if hash_path.exists() and not force:
        with open(hash_path, "r") as f:
            prev_hashes = json.load(f)

    new_hashes, changed = {}, []
    skipped = 0

    for doc in docs:
        url = doc.metadata.get("source", "")
        curr_hash = hashlib.sha256(doc.page_content.encode()).hexdigest()
        new_hashes[url] = curr_hash
        doc.metadata["content_hash"] = curr_hash

        if url in prev_hashes and prev_hashes[url] == curr_hash:
            skipped += 1
        else:
            changed.append(doc)

    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(hash_path, "w") as f:
        json.dump(new_hashes, f, indent=2)
    return changed, skipped


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. Chunk & Index
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def chunk_and_index(docs: List[Document]):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=CHUNK_SEPARATORS
    )
    chunks = splitter.split_documents(docs)
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    Chroma.from_documents(
        documents=chunks, embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIR, collection_name=CHROMA_COLLECTION_NAME
    )
    return len(chunks)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. Execution Logic
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def run_ingestion(force: bool = False):
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"--- STARTING RUN {run_id} ---")

    if not GOOGLE_API_KEY:
        logger.error("API Key missing")
        return

    # 1. Load & Fetch
    registry = load_url_registry()
    raw_docs, failures = fetch_urls(registry)
    if not raw_docs:
        logger.error("No docs fetched")
        return

    # 2. Process
    norm_docs = normalise_documents(raw_docs)
    quality_docs, rejections = validate_content_quality(norm_docs)
    changed_docs, skipped = filter_unchanged_documents(quality_docs, force)

    if not changed_docs:
        logger.info("No changes found.")
        update_last_refreshed() # Content is up to date
        return

    # 3. Index
    try:
        chunk_count = chunk_and_index(changed_docs)
        logger.info(f"Indexed {chunk_count} chunks.")
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            logger.warning("⚠️ QUOTA EXCEEDED: Data embedding failed. The system will continue using existing data.")
            logger.warning("To resolve: Check your Google AI Studio billing or wait for the quota reset.")
        else:
            logger.error(f"Ingestion failed: {e}")
            # We don't raise here, so the server can still boot Stage 2 & 3

    # 4. Output State
    update_last_refreshed()
    logger.info(f"--- RUN {run_id} COMPLETE ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    run_ingestion(force=args.force)
