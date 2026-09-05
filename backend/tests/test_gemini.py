import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.config import settings
from backend.agents.gemini_client import call_gemini

def run_test():
    print("=======================================================================")
    print("                RecoverAI Gemini API Connectivity Test")
    print("=======================================================================")
    
    key = settings.GEMINI_API_KEY
    if not key or key == "your_gemini_api_key_here" or not key.strip():
        print("[-] Error: GEMINI_API_KEY is not set in your .env file!")
        print("    Please create a '.env' file based on '.env.example' and fill in your key.")
        sys.exit(1)
        
    masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "..."
    print(f"[+] Key detected: {masked_key}")
    print("[+] Sending test request to Gemini API (gemini-1.5-flash)...")
    
    try:
        response = call_gemini("Write the word PASS in uppercase. No other text.")
        print(f"[+] Raw response received: '{response}'")
        
        if response and "PASS" in response.upper():
            print("[+] SUCCESS: Gemini integration is fully functional and responding!")
            sys.exit(0)
        else:
            print(f"[-] Warning: Received unexpected response content: '{response}'")
            sys.exit(1)
            
    except Exception as e:
        print(f"[-] FAILURE: Gemini test request failed!")
        print(f"    Error Details: {e}")
        print("    Please verify your network connection and that the GEMINI_API_KEY is valid.")
        sys.exit(1)

if __name__ == "__main__":
    run_test()
