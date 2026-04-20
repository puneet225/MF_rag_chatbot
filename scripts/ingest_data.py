"""
Phase 4 — Data Ingestion Pipeline
==================================

Reads the URL allowlist from config/url_registry.json and executes:
  1. Fetch   — Per-URL HTML scraping via AsyncHtmlLoader (Playwright).
  2. Normalise — Html2TextTransformer + cleaning + metadata enrichment.
  3. Quality  — Reject documents below MIN_CONTENT_LENGTH or missing
                financial keywords.
  4. Hash     — SHA-256 of each document for change detection across runs.
  5. Chunk    — RecursiveCharacterTextSplitter (800 chars / 100 overlap).
  6. Embed    — Google Gemini Embedding (models/gemini-embedding-001).
  7. Index    — Upsert into ChromaDB (PersistentClient, hdfc_funds collection).
  8. Manifest — Write ingest_manifest.json with run metadata.

Usage:
  python scripts/ingest_data.py            # standard run
  python scripts/ingest_data.py --force    # ignore content hashes, re-embed all

This script is executed by the Docker `ingestion` service on startup,
or manually during local development.
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

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# ─── Bootstrap ────────────────────────────────────────────────────────────────
# Add project root to path so config can be imported when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingestion")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. URL Registry Loader
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_url_registry() -> List[Dict[str, str]]:
    """Load and validate the URL registry from config/url_registry.json."""
    if not URL_REGISTRY_PATH.exists():
        raise FileNotFoundError(
            f"URL registry not found at {URL_REGISTRY_PATH}. "
            "Create config/url_registry.json with the allowlisted URLs."
        )

    with open(URL_REGISTRY_PATH, "r") as f:
        registry = json.load(f)

    if not isinstance(registry, list) or len(registry) == 0:
        raise ValueError("URL registry must be a non-empty JSON array.")

    for entry in registry:
        required = ["url", "scheme_name", "scheme_id", "amc", "source_type"]
        missing = [k for k in required if k not in entry]
        if missing:
            raise ValueError(
                f"Registry entry missing required fields {missing}: {entry}"
            )

    logger.info(f"Loaded URL registry: {len(registry)} schemes")
    return registry


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Per-URL Fetching with Individual Error Handling
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def fetch_urls(registry: List[Dict[str, str]]) -> tuple[List[Document], List[Dict]]:
    """
    Fetch HTML for each URL individually. Returns successfully loaded
    documents and a list of failure records.
    """
    urls = [entry["url"] for entry in registry]
    url_to_meta = {entry["url"]: entry for entry in registry}

    successful_docs: List[Document] = []
    failures: List[Dict] = []

    for url in urls:
        try:
            logger.info(f"  Fetching: {url}")
            loader = AsyncHtmlLoader([url])
            docs = loader.load()
            if docs and docs[0].page_content.strip():
                # Attach registry metadata to the document
                docs[0].metadata["registry"] = url_to_meta[url]
                successful_docs.append(docs[0])
                logger.info(f"  ✓ Success: {url} ({len(docs[0].page_content)} chars)")
            else:
                failures.append({"url": url, "error": "Empty response body"})
                logger.warning(f"  ✗ Empty response: {url}")
        except Exception as e:
            failures.append({"url": url, "error": str(e)})
            logger.error(f"  ✗ Failed: {url} — {e}")

    return successful_docs, failures


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Normalise & Clean
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def normalise_documents(docs: List[Document]) -> List[Document]:
    """
    Convert raw HTML to plain text, strip blank lines, and attach
    rich metadata from the URL registry entry.
    """
    html2text = Html2TextTransformer()
    docs_transformed = html2text.transform_documents(docs)

    current_date = datetime.date.today().strftime("%Y-%m-%d")
    processed: List[Document] = []

    for doc in docs_transformed:
        registry_meta = doc.metadata.pop("registry", {})

        # Clean text: strip blank lines and excess whitespace
        text = "\n".join(
            line.strip() for line in doc.page_content.split("\n") if line.strip()
        )
        doc.page_content = text

        # Enrich metadata from the registry
        doc.metadata.update({
            "source": registry_meta.get("url", doc.metadata.get("source", "")),
            "scheme_name": registry_meta.get("scheme_name", ""),
            "scheme_id": registry_meta.get("scheme_id", ""),
            "amc": registry_meta.get("amc", "HDFC Mutual Fund"),
            "source_type": registry_meta.get("source_type", "groww_scheme_page"),
            "last_updated": current_date,
        })

        processed.append(doc)

    return processed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Content Quality Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def validate_content_quality(docs: List[Document]) -> tuple[List[Document], List[str]]:
    """
    Reject documents that are too short or don't contain financial keywords.
    Returns (passed_docs, list_of_rejection_reasons).
    """
    passed: List[Document] = []
    rejections: List[str] = []

    for doc in docs:
        url = doc.metadata.get("source", "unknown")
        text_lower = doc.page_content.lower()

        # Check 1: Minimum length
        if len(doc.page_content) < MIN_CONTENT_LENGTH:
            reason = f"REJECTED {url}: Content too short ({len(doc.page_content)} chars < {MIN_CONTENT_LENGTH})"
            logger.warning(reason)
            rejections.append(reason)
            continue

        # Check 2: Must contain at least one financial keyword
        has_keyword = any(kw in text_lower for kw in QUALITY_KEYWORDS)
        if not has_keyword:
            reason = f"REJECTED {url}: No financial keywords found"
            logger.warning(reason)
            rejections.append(reason)
            continue

        passed.append(doc)

    return passed, rejections


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. Content Hashing for Change Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of document text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_previous_hashes() -> Dict[str, str]:
    """Load content hashes from the previous ingestion run."""
    hash_path = MANIFESTS_DIR / "content_hashes.json"
    if hash_path.exists():
        with open(hash_path, "r") as f:
            return json.load(f)
    return {}


def save_content_hashes(hashes: Dict[str, str]) -> None:
    """Persist content hashes for the current run."""
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    hash_path = MANIFESTS_DIR / "content_hashes.json"
    with open(hash_path, "w") as f:
        json.dump(hashes, f, indent=2)
    logger.info(f"Content hashes saved to {hash_path}")


def filter_unchanged_documents(
    docs: List[Document], force: bool = False
) -> tuple[List[Document], int]:
    """
    Compare document hashes against the previous run. Skip documents
    whose content hasn't changed (unless --force is used).
    Returns (changed_docs, skipped_count).
    """
    if force:
        # Compute and save hashes but don't skip anything
        new_hashes = {}
        for doc in docs:
            url = doc.metadata.get("source", "")
            new_hashes[url] = compute_content_hash(doc.page_content)
            doc.metadata["content_hash"] = new_hashes[url]
        save_content_hashes(new_hashes)
        return docs, 0

    previous_hashes = load_previous_hashes()
    new_hashes: Dict[str, str] = {}
    changed_docs: List[Document] = []
    skipped = 0

    for doc in docs:
        url = doc.metadata.get("source", "")
        current_hash = compute_content_hash(doc.page_content)
        new_hashes[url] = current_hash
        doc.metadata["content_hash"] = current_hash

        if url in previous_hashes and previous_hashes[url] == current_hash:
            logger.info(f"  ⊘ Unchanged (skipped): {url}")
            skipped += 1
        else:
            changed_docs.append(doc)

    save_content_hashes(new_hashes)
    return changed_docs, skipped


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. Chunk
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def chunk_documents(docs: List[Document]) -> List[Document]:
    """Split documents into semantically meaningful chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=CHUNK_SEPARATORS,
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Chunking complete: {len(docs)} documents → {len(chunks)} chunks")
    return chunks


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. Embed & Index
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def embed_and_index(chunks: List[Document]) -> None:
    """Generate embeddings and upsert into ChromaDB."""
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name=CHROMA_COLLECTION_NAME,
    )
    logger.info(
        f"Indexed {len(chunks)} chunks → "
        f"ChromaDB at {CHROMA_PERSIST_DIR}/{CHROMA_COLLECTION_NAME}"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. Ingest Manifest
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def write_manifest(
    run_id: str,
    registry_count: int,
    fetch_successes: int,
    fetch_failures: List[Dict],
    quality_rejections: List[str],
    skipped_unchanged: int,
    total_chunks: int,
) -> None:
    """Write a JSON manifest summarising this ingestion run."""
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_id": run_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "urls_in_registry": registry_count,
        "urls_fetched_ok": fetch_successes,
        "urls_failed": len(fetch_failures),
        "failures": fetch_failures,
        "quality_rejections": quality_rejections,
        "documents_skipped_unchanged": skipped_unchanged,
        "total_chunks_indexed": total_chunks,
        "chroma_persist_dir": CHROMA_PERSIST_DIR,
        "chroma_collection": CHROMA_COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
    }

    manifest_path = MANIFESTS_DIR / "ingest_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Manifest written to {manifest_path}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main Pipeline Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def ingest_data(force: bool = False) -> Dict[str, Any]:
    """
    Execute the full ingestion pipeline.

    Args:
        force: If True, re-embed all documents regardless of content hash.

    Returns:
        Summary dict with run statistics.
    """
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"{'='*60}")
    logger.info(f"INGESTION RUN {run_id} — {'FORCED' if force else 'INCREMENTAL'}")
    logger.info(f"{'='*60}")

    # Pre-flight check
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY not found. Add it to your .env file.")
        return {"error": "GOOGLE_API_KEY missing"}

    # Stage 1: Load registry
    logger.info("[1/7] Loading URL registry...")
    registry = load_url_registry()

    # Stage 2: Fetch
    logger.info(f"[2/7] Fetching {len(registry)} URLs...")
    raw_docs, fetch_failures = fetch_urls(registry)
    logger.info(
        f"  Fetch summary: {len(raw_docs)} succeeded, "
        f"{len(fetch_failures)} failed"
    )

    if not raw_docs:
        logger.error("No documents fetched successfully. Aborting.")
        write_manifest(run_id, len(registry), 0, fetch_failures, [], 0, 0)
        return {"error": "All URLs failed to fetch"}

    # Stage 3: Normalise
    logger.info("[3/7] Normalising documents...")
    normalised_docs = normalise_documents(raw_docs)

    # Stage 4: Quality validation
    logger.info("[4/7] Validating content quality...")
    quality_docs, quality_rejections = validate_content_quality(normalised_docs)
    logger.info(
        f"  Quality: {len(quality_docs)} passed, "
        f"{len(quality_rejections)} rejected"
    )

    if not quality_docs:
        logger.error("No documents passed quality validation. Aborting.")
        write_manifest(
            run_id, len(registry), len(raw_docs),
            fetch_failures, quality_rejections, 0, 0
        )
        return {"error": "All documents failed quality validation"}

    # Stage 5: Content hash / change detection
    logger.info("[5/7] Checking content hashes for changes...")
    changed_docs, skipped_count = filter_unchanged_documents(quality_docs, force)
    logger.info(
        f"  Hash check: {len(changed_docs)} changed, {skipped_count} unchanged"
    )

    if not changed_docs:
        logger.info("No content changes detected. Skipping embed/index.")
        write_manifest(
            run_id, len(registry), len(raw_docs),
            fetch_failures, quality_rejections, skipped_count, 0
        )
        return {"status": "no_changes", "skipped": skipped_count}

    # Stage 6: Chunk
    logger.info("[6/7] Chunking documents...")
    chunks = chunk_documents(changed_docs)

    # Stage 7: Embed & Index
    logger.info("[7/7] Embedding & indexing into ChromaDB...")
    embed_and_index(chunks)

    # Write manifest
    write_manifest(
        run_id, len(registry), len(raw_docs),
        fetch_failures, quality_rejections, skipped_count, len(chunks)
    )

    logger.info(f"{'='*60}")
    logger.info(f"INGESTION RUN {run_id} COMPLETE — {len(chunks)} chunks indexed")
    logger.info(f"{'='*60}")

    return {
        "status": "success",
        "run_id": run_id,
        "chunks_indexed": len(chunks),
        "urls_failed": len(fetch_failures),
        "skipped_unchanged": skipped_count,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HDFC Mutual Fund Data Ingestion")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-embedding of all documents, ignoring content hashes.",
    )
    args = parser.parse_args()
    ingest_data(force=args.force)
