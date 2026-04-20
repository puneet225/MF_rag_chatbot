import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from core.graph import app_graph

load_dotenv()

def test_routing():
    print("--- Phase 5: LangGraph Routing Verification ---")
    
    # Test Cases: (Query, Expected Intent/Node Path)
    test_cases = [
        ("What is the expense ratio of HDFC Mid Cap?", "retrieval"),
        ("Which HDFC fund is best for long term growth?", "refusal"),
        ("Hello, how are you?", "greeting"),
        ("My Aadhaar is 1234 5678 9012, tell me about SIP.", "privacy_risk")
    ]
    
    config = {"configurable": {"thread_id": "test_thread"}}
    
    for query, expected in test_cases:
        print(f"\nTesting Query: '{query}'")
        state = {"messages": [HumanMessage(content=query)]}
        
        # Run the graph
        result = app_graph.invoke(state, config)
        
        actual_intent = result.get("intent")
        print(f"Detected Intent: {actual_intent}")
        
        # Check if response was generated (refusal/greeting/generation)
        response = result.get("response", "No response generated")
        print(f"Response snippet: {response[:100]}...")
        
        if actual_intent == expected or (expected == "retrieval" and actual_intent == "factual"):
            print(f"✅ PASSED")
        else:
            print(f"❌ FAILED (Expected approx {expected}, got {actual_intent})")

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Set GOOGLE_API_KEY in .env first.")
    else:
        test_routing()
