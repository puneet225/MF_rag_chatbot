"""
Tests for the FastAPI endpoints (main.py).

Uses FastAPI's TestClient — no real server needed. LangGraph is mocked
to avoid requiring a GOOGLE_API_KEY or ChromaDB during CI.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Health Endpoint
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestHealthEndpoint:

    def test_health_returns_200(self):
        """GET /health should return 200 with status ok."""
        from main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert "version" in data

    def test_health_response_structure(self):
        """Health response should have exactly the expected keys."""
        from main import app
        client = TestClient(app)
        response = client.get("/health")
        data = response.json()
        expected_keys = {"status", "service", "version"}
        assert set(data.keys()) == expected_keys


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Chat Endpoint (Mocked LangGraph)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestChatEndpoint:

    @patch("main.app_graph")
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"})
    def test_chat_returns_factual_response(self, mock_graph):
        """POST /chat with a factual query should return a valid response."""
        mock_graph.invoke.return_value = {
            "response": "The expense ratio is 0.74%.",
            "intent": "factual",
            "citation": "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        }

        from main import app
        client = TestClient(app)
        response = client.post("/chat", json={
            "message": "What is the expense ratio of HDFC Mid Cap?",
            "thread_id": "test-thread-1"
        })

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["intent"] == "factual"
        assert data["citation"] is not None

    @patch("main.app_graph")
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"})
    def test_chat_returns_advisory_refusal(self, mock_graph):
        """POST /chat with an advisory query should return intent=advisory."""
        mock_graph.invoke.return_value = {
            "response": "I am a facts-only assistant...",
            "intent": "advisory",
            "citation": "https://www.amfiindia.com/investor-corner",
        }

        from main import app
        client = TestClient(app)
        response = client.post("/chat", json={
            "message": "Should I invest in HDFC Mid Cap?",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "advisory"

    @patch("main.app_graph")
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"})
    def test_chat_handles_graph_error_gracefully(self, mock_graph):
        """If the graph throws, API should return 500 with a generic message."""
        mock_graph.invoke.side_effect = RuntimeError("LLM quota exceeded")

        from main import app
        client = TestClient(app)
        response = client.post("/chat", json={
            "message": "What is the NAV?",
        })

        assert response.status_code == 500
        data = response.json()
        # Should NOT leak the actual error message
        assert "quota" not in data["detail"].lower()
        assert "internal error" in data["detail"].lower()

    def test_chat_missing_message_returns_422(self):
        """POST /chat without a message field should return 422."""
        from main import app
        client = TestClient(app)
        response = client.post("/chat", json={})
        assert response.status_code == 422

    @patch("main.app_graph")
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test_key"})
    def test_chat_default_thread_id(self, mock_graph):
        """If thread_id is not provided, it should default to 'default_user'."""
        mock_graph.invoke.return_value = {
            "response": "Hello!",
            "intent": "greeting",
            "citation": "",
        }

        from main import app
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hi"})

        assert response.status_code == 200
        # Verify the graph was called with the default thread_id
        call_args = mock_graph.invoke.call_args
        config = call_args[0][1]  # second positional arg is config
        assert config["configurable"]["thread_id"] == "default_user"
