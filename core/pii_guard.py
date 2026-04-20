"""
Phase 7.2 — PII Detection Guard
================================

Standalone module for detecting personally identifiable information (PII)
in user input. Called by the safety_guard_node in the LangGraph pipeline
to block processing before any retrieval or LLM call occurs.

Detected PII types:
  - PAN (Indian Permanent Account Number)
  - Aadhaar (Indian Unique Identity Number)
  - Email addresses
  - Indian mobile phone numbers
  - Bank account numbers (heuristic: 9–18 digit sequences)

Design decisions:
  - Regex-based (no ML model) for determinism and zero latency.
  - Returns structured results so the caller can log the detection type
    without logging the actual PII value.
  - False-positive-conscious: uses word boundaries and anchored patterns
    to avoid matching inside normal financial text.
"""

import re
from typing import List, Dict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PII Pattern Definitions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PII_PATTERNS = [
    {
        "type": "pan",
        "label": "PAN (Permanent Account Number)",
        # PAN format: 5 uppercase letters, 4 digits, 1 uppercase letter
        # Word boundaries prevent matching inside normal words like "FUNDS1234X"
        "pattern": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    },
    {
        "type": "aadhaar",
        "label": "Aadhaar Number",
        # Aadhaar: 12 digits starting with 2-9, optionally space/dash separated
        # Format: XXXX XXXX XXXX or XXXX-XXXX-XXXX or XXXXXXXXXXXX
        "pattern": re.compile(
            r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"
        ),
    },
    {
        "type": "email",
        "label": "Email Address",
        "pattern": re.compile(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        ),
    },
    {
        "type": "phone",
        "label": "Indian Phone Number",
        # Indian mobile: optional +91/91 prefix, then 10 digits starting 6-9
        "pattern": re.compile(
            r"(?:\+?91[\s\-]?)?[6-9]\d{9}\b"
        ),
    },
    {
        "type": "bank_account",
        "label": "Bank Account Number (heuristic)",
        # Heuristic: 9-18 continuous digits not part of a larger number
        # This will have some false positives on very long numeric strings,
        # but errs on the side of caution per the Problem Statement.
        "pattern": re.compile(r"\b\d{9,18}\b"),
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_pii(text: str) -> List[Dict[str, str]]:
    """
    Scan text for PII patterns.

    Args:
        text: The user's input message.

    Returns:
        List of dicts, each with keys:
          - "type":  PII category (pan, aadhaar, email, phone, bank_account)
          - "label": Human-readable label for logging/UI
          - "match": The matched substring (for internal logging; do NOT
                     expose to the user or persist in thread history)

        Empty list → no PII detected → safe to proceed.
    """
    detections: List[Dict[str, str]] = []

    for entry in PII_PATTERNS:
        matches = entry["pattern"].findall(text)
        for match in matches:
            detections.append({
                "type": entry["type"],
                "label": entry["label"],
                "match": match,
            })

    return detections


def contains_pii(text: str) -> bool:
    """Quick boolean check — does the text contain any PII?"""
    return len(detect_pii(text)) > 0
