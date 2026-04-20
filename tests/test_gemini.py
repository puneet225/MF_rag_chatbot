import os
import time
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
print(f"API Key present: {bool(api_key)}")

genai.configure(api_key=api_key)

try:
    print("Testing generateContent using models/gemini-1.5-flash...")
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    start = time.time()
    response = model.generate_content("Say hello in 1 word", request_options={"timeout": 10})
    print(f"Resp: {response.text.strip()}, Time: {time.time()-start:.2f}s")
except Exception as e:
    print(f"Error 1.5: {e}")

try:
    print("Testing generateContent using models/gemini-3.1-flash-lite-preview...")
    model = genai.GenerativeModel("models/gemini-3.1-flash-lite-preview")
    start = time.time()
    response = model.generate_content("Say hello in 1 word", request_options={"timeout": 10})
    print(f"Resp: {response.text.strip()}, Time: {time.time()-start:.2f}s")
except Exception as e:
    print(f"Error 3.1: {e}")

try:
    print("Testing embedContent using models/gemini-embedding-001...")
    start = time.time()
    response = genai.embed_content(model="models/gemini-embedding-001", content="hello", task_type="retrieval_document")
    print(f"Resp length: {len(response['embedding'])}, Time: {time.time()-start:.2f}s")
except Exception as e:
    print(f"Error Embed: {e}")
