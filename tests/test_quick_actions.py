import requests
import time
import uuid

def test_quick_actions():
    print("--- Testing Quick Action Chips (FundFact API) ---")
    
    url = "http://localhost:8001/chat"
    
    test_cases = [
        "What is the latest NAV for HDFC Mid Cap?",
        "Show me the expense ratio for HDFC Top 100",
        "What are the exit load details for HDFC Flexi Cap?",
        "Minimum SIP amount for HDFC Index Fund?"
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Sending: '{test}'")
        session_id = str(uuid.uuid4())
        
        try:
            start_time = time.time()
            response = requests.post(
                url,
                json={"message": test, "thread_id": session_id},
                timeout=90
            )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                bot_res = data.get("response", "No response text")
                intent = data.get("intent", "unknown")
                print(f"  ✅ SUCCESS ({elapsed:.2f}s) | Intent: {intent}")
                print(f"  🤖 Bot: {bot_res[:150]}...")
                results.append((True, test, bot_res, intent))
            else:
                print(f"  ❌ FAILED | Status Code: {response.status_code}")
                results.append((False, test, "API Error", "error"))
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ FAILED | Exception: {e}")
            results.append((False, test, str(e), "error"))
            
    print("\n--- Summary ---")
    passed = sum(1 for r in results if r[0])
    print(f"Passed {passed} / {len(test_cases)} tests.")

if __name__ == "__main__":
    test_quick_actions()
