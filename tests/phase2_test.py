import sys
import os
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from orchestrator.run_pipeline import fetch_urls

def test_single_scrape():
    # Corrected URL from registry
    test_registry = [
        {
            "url": "https://groww.in/mutual-funds/hdfc-top-100-fund-direct-plan-growth",
            "scheme_name": "HDFC Top 100 Fund",
            "scheme_id": "hdfc_top_100",
            "source_type": "groww_scheme_page"
        }
    ]
    
    print("--- PHASE 2 TEST: HIGH-FIDELITY SCRAPE ---")
    docs, failures = fetch_urls(test_registry)
    
    if failures:
        print(f"FAILED: {failures[0]['error']}")
        sys.exit(1)
        
    if not docs:
        print("FAILED: No documents returned")
        sys.exit(1)
        
    content = docs[0].page_content
    print(f"SUCCESS: Captured {len(content)} bytes")
    
    if len(content) > 5000:
        print("PHASE 2 PASSED.")
        sys.exit(0)
    else:
        print("PHASE 2 FAILED: Content too short.")
        sys.exit(1)

if __name__ == "__main__":
    test_single_scrape()
