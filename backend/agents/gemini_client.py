import requests
import json
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

def call_gemini(prompt: str, system_instruction: str = None) -> str:
    """
    Dispatches a request to the Gemini API using the configured GEMINI_API_KEY.
    If the key is present but the request fails, raises a RuntimeError to prevent
    silently pretending that the AI worked.
    """
    key = settings.GEMINI_API_KEY
    if not key or key == "your_gemini_api_key_here" or not key.strip():
        # If no key is set, return None so the calling agent knows to run in heuristic/simulation mode
        return None

    # Using the standard beta API endpoint for gemini-1.5-flash
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    try:
        logger.info("Sending prompt to Gemini API...")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            error_detail = response.text
            try:
                err_json = response.json()
                error_detail = err_json.get("error", {}).get("message", response.text)
            except:
                pass
            error_msg = f"Gemini API Server Error ({response.status_code}): {error_detail}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
            
        res_data = response.json()
        
        # Parse the response text
        candidates = res_data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini API response contained no candidates.")
            
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Gemini API response contained no content parts.")
            
        generated_text = parts[0].get("text", "")
        return generated_text.strip()
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to reach Gemini API Endpoint: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
