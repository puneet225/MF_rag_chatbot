import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Test the exact same initialization as core/nodes.py
print("Testing Langchain Gemini integration...")
try:
    llm = ChatGoogleGenerativeAI(model="models/gemini-3.1-flash-lite-preview", temperature=0)
    print("Calling invoke...")
    response = llm.invoke("Hi")
    print(f"Response: {response.content}")
except Exception as e:
    print(f"Error: {e}")
