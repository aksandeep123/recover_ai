import json
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class RootCauseAgent:
    def __init__(self):
        pass

    def _calculate_heuristics(self, raw_reason: str) -> dict:
        """Fallback heuristics for parsing decline codes."""
        raw_clean = str(raw_reason).upper().strip()

        if "INSUFFICIENT" in raw_clean or "BALANCE" in raw_clean or "LIMIT" in raw_clean:
            root_cause = "insufficient_funds"
            explanation = "The customer's bank account or card does not have enough funds or has reached its limit."
        elif "EXPIRED" in raw_clean or "EXPIRY" in raw_clean:
            root_cause = "expired_payment_method"
            explanation = "The payment method has expired and is no longer valid."
        elif "TIMEOUT" in raw_clean or "GATEWAY_TIMEOUT" in raw_clean or "RESPONSE" in raw_clean:
            root_cause = "timeout"
            explanation = "The connection between the payment gateway and the bank timed out during processing."
        elif "AUTH" in raw_clean or "OTP" in raw_clean or "SECURE" in raw_clean or "PIN" in raw_clean:
            root_cause = "authentication_failure"
            explanation = "The customer failed to complete the 3D secure, OTP, or PIN verification step."
        elif "DECLINE" in raw_clean or "HONOR" in raw_clean:
            root_cause = "bank_decline"
            explanation = "The transaction was declined by the customer's bank without a specific error code."
        elif "TEMPORARY" in raw_clean or "SWITCH" in raw_clean or "MAINTENANCE" in raw_clean or "GATEWAY_ERROR" in raw_clean:
            root_cause = "temporary_bank_issue"
            explanation = "The issuing bank is experiencing a temporary network issue or downtime."
        elif "ABANDONED" in raw_clean or "CHECKOUT" in raw_clean:
            root_cause = "checkout_abandonment"
            explanation = "The customer navigated away from the payment screen before finalizing the transaction."
        elif "INVALID" in raw_clean or "CARD_NUMBER" in raw_clean:
            root_cause = "invalid_payment_method"
            explanation = "The payment details entered (card number, CVV, or VPA) are invalid."
        elif "RECURRING" in raw_clean or "AUTO" in raw_clean:
            root_cause = "recurring_payment_failure"
            explanation = "Recurring auto-decline triggered by bank subscription mandate policies."
        else:
            root_cause = "unknown"
            explanation = f"An unknown error occurred during transaction processing: '{raw_reason}'."

        return {
            "root_cause": root_cause,
            "explanation": explanation
        }

    def diagnose(self, raw_reason: str) -> dict:
        """
        Classifies failure reasons into high-level root cause categories using Gemini when available.
        """
        heuristics = self._calculate_heuristics(raw_reason)

        try:
            from backend.agents.gemini_client import call_gemini
            prompt = f"Diagnose raw payment failure code: '{raw_reason}'. Classify it into one of these categories: insufficient_funds, bank_decline, temporary_bank_issue, timeout, authentication_failure, expired_payment_method, invalid_payment_method, checkout_abandonment, recurring_payment_failure, unknown. Also provide a simple, human-friendly explanation of why it failed. Output raw JSON only with keys: root_cause, explanation."
            system_instruction = "You are a Payment Diagnostics Agent. Analyze raw payment gateway error codes and classify them into standardized categories. Return ONLY a valid JSON object. Do not include markdown code blocks."
            
            llm_text = call_gemini(prompt, system_instruction)
            if llm_text:
                clean_text = llm_text.strip()
                if clean_text.startswith("```"):
                    lines = clean_text.split("\n")
                    clean_text = "\n".join(lines[1:-1]) if lines[0].startswith("```") else clean_text
                
                if clean_text.startswith("json"):
                    clean_text = clean_text[4:].strip()
                
                parsed = json.loads(clean_text)
                
                # Assert valid category, fallback if Gemini invents a category
                rc = parsed.get("root_cause", heuristics["root_cause"])
                valid_causes = ["insufficient_funds", "bank_decline", "temporary_bank_issue", "timeout", "authentication_failure", "expired_payment_method", "invalid_payment_method", "checkout_abandonment", "recurring_payment_failure", "unknown"]
                if rc not in valid_causes:
                    rc = heuristics["root_cause"]

                return {
                    "root_cause": rc,
                    "explanation": parsed.get("explanation", heuristics["explanation"])
                }
        except Exception as e:
            if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
                raise RuntimeError(f"RootCauseAgent Gemini API Error: {e}")
            logger.warning(f"Gemini not configured or failed. Using heuristics fallback: {e}")

        return heuristics
