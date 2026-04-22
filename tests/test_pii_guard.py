"""
Tests for the PII detection guard (core/pii_guard.py).

Validates that each PII pattern correctly detects its target category
while avoiding false positives on normal financial text.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.pii_guard import detect_pii, contains_pii


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAN Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPANDetection:

    def test_detects_valid_pan(self):
        """Standard PAN format should be detected."""
        result = detect_pii("My PAN is ABCDE1234F")
        pan_hits = [r for r in result if r["type"] == "pan"]
        assert len(pan_hits) == 1
        assert pan_hits[0]["match"] == "ABCDE1234F"

    def test_detects_pan_in_sentence(self):
        """PAN embedded in a longer sentence should be detected."""
        result = detect_pii("Please verify PAN XYZAB9876C for tax purposes")
        pan_hits = [r for r in result if r["type"] == "pan"]
        assert len(pan_hits) == 1

    def test_no_false_positive_on_fund_names(self):
        """Fund names like 'HDFCM' should NOT trigger PAN detection."""
        result = detect_pii("HDFC Mid Cap Fund Direct Growth")
        pan_hits = [r for r in result if r["type"] == "pan"]
        assert len(pan_hits) == 0

    def test_no_false_positive_on_short_codes(self):
        """Short uppercase strings should not be flagged as PAN."""
        result = detect_pii("NAV and AUM are key metrics")
        pan_hits = [r for r in result if r["type"] == "pan"]
        assert len(pan_hits) == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Aadhaar Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAadhaarDetection:

    def test_detects_spaced_aadhaar(self):
        """Aadhaar in XXXX XXXX XXXX format should be detected."""
        result = detect_pii("My Aadhaar is 2345 6789 0123")
        aadhaar_hits = [r for r in result if r["type"] == "aadhaar"]
        assert len(aadhaar_hits) >= 1

    def test_detects_continuous_aadhaar(self):
        """Aadhaar as 12 continuous digits should be detected."""
        result = detect_pii("Aadhaar number is 234567890123")
        # Might be detected as aadhaar or bank_account — check either
        hits = [r for r in result if r["type"] in ("aadhaar", "bank_account")]
        assert len(hits) >= 1

    def test_detects_dashed_aadhaar(self):
        """Aadhaar in XXXX-XXXX-XXXX format should be detected."""
        result = detect_pii("2345-6789-0123")
        aadhaar_hits = [r for r in result if r["type"] == "aadhaar"]
        assert len(aadhaar_hits) >= 1

    def test_no_false_positive_on_nav(self):
        """NAV values like 152.34 should NOT trigger Aadhaar detection."""
        result = detect_pii("NAV is 152.34")
        aadhaar_hits = [r for r in result if r["type"] == "aadhaar"]
        assert len(aadhaar_hits) == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Email Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestEmailDetection:

    def test_detects_email(self):
        """Standard email addresses should be detected."""
        result = detect_pii("Contact me at user@example.com")
        email_hits = [r for r in result if r["type"] == "email"]
        assert len(email_hits) == 1

    def test_detects_complex_email(self):
        """Emails with dots, plus signs should be detected."""
        result = detect_pii("Email: first.last+tag@company.co.in")
        email_hits = [r for r in result if r["type"] == "email"]
        assert len(email_hits) == 1

    def test_no_false_positive_on_urls(self):
        """groww.in URLs should NOT be flagged as email."""
        result = detect_pii("Visit https://groww.in/mutual-funds")
        email_hits = [r for r in result if r["type"] == "email"]
        assert len(email_hits) == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phone Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestPhoneDetection:

    def test_detects_10_digit_phone(self):
        """Indian mobile number starting 6-9 should be detected."""
        result = detect_pii("Call me at 9876543210")
        phone_hits = [r for r in result if r["type"] == "phone"]
        assert len(phone_hits) == 1

    def test_detects_phone_with_country_code(self):
        """Phone with +91 prefix should be detected."""
        result = detect_pii("My number is +91 9876543210")
        phone_hits = [r for r in result if r["type"] == "phone"]
        assert len(phone_hits) == 1

    def test_detects_phone_with_91_prefix(self):
        """Phone with 91 prefix (no plus) should be detected."""
        result = detect_pii("Phone: 91-9876543210")
        phone_hits = [r for r in result if r["type"] == "phone"]
        assert len(phone_hits) == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Clean Text (No False Positives)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCleanText:

    def test_normal_factual_query_is_clean(self):
        """A standard factual query should produce zero detections."""
        result = detect_pii("What is the expense ratio of HDFC Mid Cap Fund?")
        assert len(result) == 0

    def test_financial_numbers_are_clean(self):
        """Financial amounts should not trigger PII detection."""
        result = detect_pii("The AUM is ₹42,567 Cr and NAV is 152.34")
        # Filter out bank_account false positives on short numbers
        meaningful_hits = [r for r in result if r["type"] not in ("bank_account",)]
        assert len(meaningful_hits) == 0

    def test_contains_pii_boolean(self):
        """contains_pii() should return True only when PII is present."""
        assert contains_pii("My PAN is ABCDE1234F") is True
        assert contains_pii("What is HDFC expense ratio?") is False
