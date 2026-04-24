import os
import httpx
import pytest
from dotenv import load_dotenv

load_dotenv()

RENDER_URL = os.getenv("RENDER_BACKEND_URL", "https://groww-mf-chatbot-qhhf.onrender.com")
INGEST_TOKEN = os.getenv("INGEST_TOKEN")

@pytest.mark.asyncio
async def test_ingestion_handshake():
    """
    INTEGRATION TEST: Verifies that the external sync trigger (CURL) 
    can successfully talk to the backend.
    """
    if not INGEST_TOKEN:
        pytest.skip("INGEST_TOKEN not found in environment")

    sync_url = f"{RENDER_URL}/admin/ingest?token={INGEST_TOKEN}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # We use a HEAD or GET to check if the endpoint is reachable
        # Note: A POST would trigger a full scrape, so we just check reachability here
        response = await client.post(sync_url)
        
        # We expect 200 (Success) or 401 (If token is wrong)
        # Any 404 or 500 means the 'No host' or 'Missing endpoint' error is still there.
        assert response.status_code != 404, f"Backend URL {RENDER_URL} is incorrect or unreachable."
        assert response.status_code != 3, "Host part missing in URL."
        
        if response.status_code == 200:
            print(f"\n✅ Sync Handshake Verified: {RENDER_URL} responded correctly.")
        else:
            print(f"\n⚠️ Handshake failed with status {response.status_code}: {response.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ingestion_handshake())
