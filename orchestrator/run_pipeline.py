"""
Phase 4 — Unified Ingestion Pipeline Orchestrator
=================================================
Handles the end-to-end ingestion flow and updates the system state.
Multi-Engine Scraper (Firefox/Chromium/Webkit) + JSON Extraction.
"""

import os
import sys
import json
import hashlib
import datetime
import argparse
import logging
import uuid
import httpx
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from dotenv import load_dotenv
# ─── Bootstrap ────────────────────────────────────────────────────────────────
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
from langchain_community.document_transformers import Html2TextTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from core.vector_store import get_vector_store
from core.retriever import invalidate_retriever_cache

load_dotenv()

ORCHESTRATOR_DIR = ROOT_DIR / "orchestrator"
LAST_REFRESHED_PATH = ORCHESTRATOR_DIR / "last_refreshed.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orchestrator.pipeline")

def update_last_refreshed():
    try:
        ORCHESTRATOR_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        with open(LAST_REFRESHED_PATH, "w") as f:
            f.write(timestamp)
        logger.info(f"Updated cache state: {timestamp}")
    except Exception as e:
        logger.error(f"Failed to update last_refreshed.txt: {e}")

def load_url_registry() -> List[Dict[str, str]]:
    if not URL_REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registry missing: {URL_REGISTRY_PATH}")
    with open(URL_REGISTRY_PATH, "r") as f:
        registry = json.load(f)
    logger.info(f"Loaded registry: {len(registry)} schemes")
    return registry

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Fetch (Multi-Engine Playwright + JSON Extraction)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def extract_from_json_data(html: str) -> str:
    """Extracts fund data and translates JSON facts into Natural Language Sentences."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script: return html
        
        data = json.loads(script.string.strip())
        props = data.get("props", {}).get("pageProps", {})
        
        def deep_find(obj, target_key):
            if isinstance(obj, dict):
                if target_key in obj: return obj[target_key]
                for v in obj.values():
                    res = deep_find(v, target_key)
                    if res: return res
            elif isinstance(obj, list):
                for item in obj:
                    res = deep_find(item, target_key)
                    if res: return res
            return None

        # ─── MASTER SOURCE MERGE (Robust Deep Search) ───
        # Use deep_find to hunt for keys anywhere in the page properties
        nav_val = deep_find(props, "nav")
        nav_date = deep_find(props, "nav_date")
        aum_val = deep_find(props, "aum")
        tax_val = deep_find(props, "tax_impact")
        exit_val = deep_find(props, "exit_load")
        expense_val = deep_find(props, "expense_ratio")
        sip_val = deep_find(props, "min_sip_investment")
        managers = deep_find(props, "fund_manager") or deep_find(props, "fund_managers")
        
        # 1. Identify the Fund Name
        scheme_name = deep_find(props, "scheme_name") or "the fund"
        
        # 2. Build Factual Sentences (The 'Digital Mirror')
        facts = []
        facts.append(f"Scheme Name: {scheme_name}.")
        
        if nav_val:
            facts.append(f"The latest Net Asset Value (NAV) for {scheme_name} is {nav_val} as of {nav_date or 'today'}.")
        
        if aum_val:
            facts.append(f"The Assets Under Management (AUM) or Fund Size for {scheme_name} is {aum_val} Cr.")
            
        if expense_val:
             facts.append(f"The Expense Ratio for {scheme_name} is {expense_val}%.")

        if exit_val:
             # Ensure we capture the full exit load string
             facts.append(f"The Exit Load for {scheme_name} is: {exit_val}.")

        if sip_val:
             facts.append(f"The Minimum SIP investment for {scheme_name} is Rs {sip_val}.")

        if tax_val:
            # Strip HTML if present
            clean_tax = re.sub('<[^<]+?>', '', str(tax_val))
            facts.append(f"Taxation and Tax Implications for {scheme_name}: {clean_tax}")

        # Adding Fund Managers
        if managers:
            if isinstance(managers, list):
                mgr_names = []
                for m in managers:
                    if isinstance(m, dict): 
                        name = m.get("person_name") or m.get("name")
                        if name: mgr_names.append(name)
                if mgr_names:
                    facts.append(f"The Fund Managers for {scheme_name} are {', '.join(mgr_names)}.")
            elif isinstance(managers, str):
                facts.append(f"The Fund Manager for {scheme_name} is {managers}.")

        # Join into a high-density factual block
        return "\n".join(facts)

    except Exception as e:
        logger.warning(f"Failed to translate __NEXT_DATA__ to Natural Language: {e}")
    return html

def fetch_urls(registry: List[Dict[str, str]]) -> tuple[List[Document], List[Dict]]:
    """Fetches fund HTML using high-fidelity HTTPX mimicry (fast & stable)."""
    url_to_meta = {entry["url"]: entry for entry in registry}
    successful_docs: List[Document] = []
    failures: List[Dict] = []
    
    # Shared Browser-Mimicry Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache"
    }

    logger.info(f"  Fetching {len(url_to_meta)} URLs via HTTPX Mimicry (Data Mirror Mode)...")
    
    with httpx.Client(headers=headers, follow_redirects=True, timeout=45.0) as client:
        for url, meta in url_to_meta.items():
            try:
                logger.info(f"  Scraping factual context: {url}")
                response = client.get(url)
                
                # Robust retry for common Groww URL patterns
                if response.status_code == 404:
                    alt_url = url.replace("-fund-", "-") if "-fund-" in url else url.replace("-direct-", "-fund-direct-")
                    response = client.get(alt_url)
                
                if response.status_code == 200:
                    # EXTRACTION + METADATA CAPTURE
                    soup = BeautifulSoup(response.text, "html.parser")
                    script = soup.find("script", id="__NEXT_DATA__")
                    nav_date_str = "unknown"
                    if script:
                        data = json.loads(script.string.strip())
                        props = data.get("props", {}).get("pageProps", {})
                        # Recursive hunt for nav_date
                        def find_key(obj, key):
                            if isinstance(obj, dict):
                                if key in obj: return obj[key]
                                for v in obj.values():
                                    res = find_key(v, key)
                                    if res: return res
                            elif isinstance(obj, list):
                                for item in obj:
                                    res = find_key(item, key)
                                    if res: return res
                            return None
                        nav_date_str = str(find_key(props, "nav_date") or find_key(props, "last_updated") or "unknown")

                    content = extract_from_json_data(response.text)
                    successful_docs.append(Document(
                        page_content=content, 
                        metadata={
                            "registry": meta,
                            "last_updated": nav_date_str
                        }
                    ))
                    logger.info(f"    ✓ Captured {len(content)} bytes (Data Date: {nav_date_str})")
                else:
                    logger.warning(f"    ✗ Failed: HTTP {response.status_code} for {url}")
                    failures.append({"url": url, "error": f"HTTP {response.status_code}"})
            except Exception as e:
                logger.warning(f"    ⚠ Network Alert for {url}: {e}")
                failures.append({"url": url, "error": str(e)})

    return successful_docs, failures

def normalise_documents(docs: List[Document]) -> List[Document]:
    for doc in docs:
        meta = doc.metadata.pop("registry", {})
        # last_updated is already in metadata from fetch_urls
        if not doc.page_content.strip().startswith("{"):
            html2text = Html2TextTransformer()
            doc_transformed = html2text.transform_documents([doc])[0]
            doc.page_content = doc_transformed.page_content
        doc.metadata.update({
            "source": meta.get("url", ""),
            "scheme_name": meta.get("scheme_name", ""),
            "scheme_id": meta.get("scheme_id", ""),
            "amc": meta.get("amc", "HDFC Mutual Fund"),
            "source_type": meta.get("source_type", "groww_scheme_page"),
        })
    return docs

def validate_content_quality(docs: List[Document]) -> tuple[List[Document], List[str]]:
    passed, rejected = [], []
    for doc in docs:
        if len(doc.page_content) < MIN_CONTENT_LENGTH:
            rejected.append(f"Short: {doc.metadata.get('source')}")
            continue
        passed.append(doc)
    return passed, rejected

def filter_unchanged_documents(docs: List[Document], force: bool = False) -> tuple[List[Document], int]:
    hash_path = MANIFESTS_DIR / "content_hashes.json"
    prev_hashes = {}
    if hash_path.exists() and not force:
        try:
            with open(hash_path, "r") as f:
                prev_hashes = json.load(f)
        except: prev_hashes = {}
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

def chunk_and_index(docs: List[Document]):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=CHUNK_SEPARATORS
    )
    chunks = splitter.split_documents(docs)
    vector_store = get_vector_store()
    
    # CLEAN MIRROR RULE: To prevent stale data (like seeing the 22nd when it's the 23rd),
    # we must remove existing documents for the funds we are updating.
    for doc in docs:
        sid = doc.metadata.get("scheme_id")
        if sid:
            try:
                logger.debug(f"  Clearing old mirror data for {sid}...")
                vector_store.delete(where={"scheme_id": sid})
            except Exception as e:
                logger.warning(f"  Could not clear old data for {sid}: {e}")

    # BATCHING: Process chunks in batches of 30 
    batch_size = 30
    logger.info(f"Indexing {len(chunks)} chunks in batches of {batch_size}...")
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        try:
            vector_store.add_documents(batch)
            logger.info(f"  ✓ Indexed batch {i//batch_size + 1}")
        except Exception as e:
            logger.error(f"  ✗ Failed indexing batch at {i}: {e}")
            raise e
            
    invalidate_retriever_cache()
    return len(chunks)

import threading

# GLOBAL LOCK: Ensures only one ingestion can run at a time to prevent 
# SQLite 'database is locked' or 'readonly' errors.
_ingestion_lock = threading.Lock()

def run_ingestion(force: bool = False) -> Dict[str, Any]:
    if not _ingestion_lock.acquire(blocking=False):
        logger.warning("Another ingestion is already in progress. Skipping this run.")
        return {"status": "skipped", "message": "Another ingestion active"}

    run_id = str(uuid.uuid4())[:8]
    stats = {"run_id": run_id, "chunks_indexed": 0, "status": "started"}
    
    try:
        logger.info(f"--- STARTING RUN {run_id} ---")
        
        if not GOOGLE_API_KEY:
            logger.error("API Key missing")
            stats["status"] = "failed: api_key_missing"
            return stats
            
        registry = load_url_registry()
        raw_docs, failures = fetch_urls(registry)
        if not raw_docs:
            logger.error("No docs successfully fetched.")
            stats["status"] = "failed: fetch_error"
            return stats
            
        norm_docs = normalise_documents(raw_docs)
        quality_docs, rejections = validate_content_quality(norm_docs)
        changed_docs, skipped = filter_unchanged_documents(quality_docs, force)
        
        if not changed_docs:
            logger.info("No data updates required.")
            update_last_refreshed()
            stats["status"] = "success: no_updates"
            return stats
            
        chunk_count = chunk_and_index(changed_docs)
        logger.info(f"Indexed {chunk_count} chunks.")
        stats["chunks_indexed"] = chunk_count
        stats["status"] = "success"
        
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        stats["status"] = f"failed: {str(e)}"
    finally:
        _ingestion_lock.release()
        
    update_last_refreshed()
    logger.info(f"--- RUN {run_id} COMPLETE ---")
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    results = run_ingestion(force=args.force)
    print(json.dumps(results, indent=2))
