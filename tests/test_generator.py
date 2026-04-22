"""
Tests for the generation layer (core/generator.py).

Tests the post-generation validation logic and citation footer injection.
No LLM calls — validation functions are pure logic.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.generator import validate_response, ensure_citation_footer


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Post-Generation Validation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestValidateResponse:

    def test_clean_2_sentence_response_passes(self):
        """A well-formed 2-sentence response should pass validation."""
        text = (
            "The expense ratio of HDFC Mid Cap Fund is 0.74% for the Direct Plan. "
            "This is one of the lowest in the mid-cap category."
        )
        result = validate_response(text)
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_clean_3_sentence_response_passes(self):
        """A 3-sentence response (the maximum) should pass."""
        text = (
            "The NAV is ₹152.34. "
            "The expense ratio is 0.74%. "
            "The fund is categorised as Very High Risk."
        )
        result = validate_response(text)
        assert result["valid"] is True

    def test_5_sentence_response_fails(self):
        """A 5-sentence response should fail the sentence count check."""
        text = (
            "Sentence one. "
            "Sentence two. "
            "Sentence three. "
            "Sentence four. "
            "Sentence five."
        )
        result = validate_response(text)
        assert result["valid"] is False
        assert any("Sentence count" in issue for issue in result["issues"])

    def test_advisory_language_detected(self):
        """Forbidden patterns like 'you should' should be flagged."""
        text = "You should invest in HDFC Mid Cap for good returns."
        result = validate_response(text)
        assert result["valid"] is False
        assert any("forbidden pattern" in issue.lower() for issue in result["issues"])

    def test_recommend_pattern_detected(self):
        """The word 'recommend' should be flagged."""
        text = "I recommend this fund for long-term growth."
        result = validate_response(text)
        assert result["valid"] is False

    def test_buy_sell_patterns_detected(self):
        """Words like 'buy' and 'sell' should be flagged."""
        text = "You can buy this fund through Groww."
        result = validate_response(text)
        assert result["valid"] is False

    def test_guarantee_pattern_detected(self):
        """The word 'guarantee' should be flagged."""
        text = "This fund can guarantee returns of 15%."
        result = validate_response(text)
        assert result["valid"] is False

    def test_footer_lines_excluded_from_sentence_count(self):
        """Citation footer should NOT count towards the 3-sentence limit."""
        text = (
            "The NAV is ₹152.34. "
            "The expense ratio is 0.74%. "
            "The exit load is 1% within 1 year.\n\n"
            "**Source:** https://groww.in/mutual-funds/hdfc-mid-cap\n"
            "*Last updated from sources: 2026-04-20*"
        )
        result = validate_response(text)
        assert result["valid"] is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Citation Footer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCitationFooter:

    def test_injects_missing_footer(self):
        """If no footer exists, it should be appended."""
        text = "The expense ratio is 0.74%."
        result = ensure_citation_footer(text, "https://groww.in/example", "2026-04-20")
        assert "**Source:**" in result
        assert "https://groww.in/example" in result
        assert "2026-04-20" in result

    def test_preserves_existing_footer(self):
        """If footer already exists, return text unchanged."""
        text = (
            "The NAV is ₹152.34.\n\n"
            "**Source:** https://groww.in/existing\n"
            "*Last updated from sources: 2026-04-19*"
        )
        result = ensure_citation_footer(text, "https://groww.in/new", "2026-04-20")
        # Should keep the original footer, not the new one
        assert "https://groww.in/existing" in result
        assert "https://groww.in/new" not in result
