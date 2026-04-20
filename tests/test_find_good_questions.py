"""
Integration test: Quick Actions against a LIVE server.

This test requires the API to be running on localhost:8001.
It is skipped automatically when the server is not reachable.

Run manually with:
  pytest tests/test_find_good_questions.py -v -m integration
"""

import requests
import uuid
import pytest


def _server_is_running():
    """Check if the API server is reachable."""
    try:
        requests.get("http://localhost:8001/health", timeout=2)
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(
    not _server_is_running(),
    reason="Requires a running API server on localhost:8001",
)
def test_quick_actions():
    url = "http://localhost:8001/chat"

    test_cases = [
        "What is the benchmark index for HDFC Mid Cap?",
        "Who is the fund manager for HDFC Flexi Cap?",
        "What is the expense ratio for HDFC Mid Cap?",
        "What is the minimum SIP amount for HDFC Flexi Cap?",
    ]

    for test in test_cases:
        session_id = str(uuid.uuid4())
        response = requests.post(
            url, json={"message": test, "thread_id": session_id}, timeout=30
        )
        assert response.status_code == 200
        bot_res = response.json().get("response", "")
        print(f"Q: {test}\nA: {bot_res[:100]}...\n")


if __name__ == "__main__":
    test_quick_actions()
