import json
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class StrategyAgent:
    def __init__(self):
        pass

    def _calculate_heuristics(self, root_cause: str, amount: float, attempts: int, clv: float, is_subscription: bool) -> dict:
        """Fallback heuristics for strategy selection."""
        # High value threshold limit check
        if amount >= settings.HIGH_VALUE_THRESHOLD_INR:
            return {
                "action": "ESCALATE_TO_HUMAN",
                "confidence": 0.95,
                "reason": f"Transaction amount ₹{amount} exceeds the high-value threshold of ₹{settings.HIGH_VALUE_THRESHOLD_INR}. Requires manual evaluation."
            }

        # Max retries policy check
        if attempts >= settings.MAX_RETRIES:
            return {
                "action": "STOP",
                "confidence": 0.99,
                "reason": f"Maximum auto recovery attempts ({settings.MAX_RETRIES}) reached. Halting automatic processes."
            }

        if root_cause == "temporary_bank_issue" or root_cause == "timeout":
            if attempts == 0:
                action = "RETRY_PAYMENT"
                confidence = 0.90
                reason = "Temporary bank or network timeout issue. Initiating immediate retry while connection might be restored."
            else:
                action = "SCHEDULE_RETRY"
                confidence = 0.80
                reason = "Repeat temporary failure. Scheduling automated retry in 30 minutes to allow bank gateway stabilization."
        
        elif root_cause == "insufficient_funds":
            action = "SEND_PAYMENT_LINK"
            confidence = 0.92
            reason = "Insufficient funds. Sending a recovery payment link to allow the customer to pay via another account or UPI."
            
        elif root_cause == "expired_payment_method":
            if is_subscription:
                action = "REQUEST_PAYMENT_METHOD_UPDATE"
                confidence = 0.95
                reason = "Expired payment method on recurring subscription. Prompting customer to update card details."
            else:
                action = "SEND_PAYMENT_LINK"
                confidence = 0.85
                reason = "Card is expired. Sending payment link for customer to enter a new card or alternative method."
                
        elif root_cause == "authentication_failure":
            action = "SEND_PAYMENT_LINK"
            confidence = 0.88
            reason = "OTP or 3D-secure authentication failed. Sending payment link to prompt customer to re-authenticate."
            
        elif root_cause == "checkout_abandonment":
            action = "SEND_PAYMENT_LINK"
            confidence = 0.85
            reason = "Abandoned checkout. Sending checkout recovery link with a soft nudge."

        elif root_cause == "bank_decline":
            if clv > 50000:
                action = "ESCALATE_TO_HUMAN"
                confidence = 0.90
                reason = "Hard bank decline on a high-value customer profile (CLV > ₹50,000). Escalating to VIP support."
            else:
                action = "SEND_PAYMENT_LINK"
                confidence = 0.75
                reason = "Bank declined transaction. Sending payment link to offer alternative payment options (UPI, netbanking)."

        else:
            action = "ESCALATE_TO_HUMAN"
            confidence = 0.70
            reason = "Complex or unclassified failure reason. Escalating to merchant support desk."

        return {
            "action": action,
            "confidence": confidence,
            "reason": reason
        }

    def recommend(self, root_cause: str, amount: float, attempts: int, clv: float, is_subscription: bool) -> dict:
        """
        Recommends the best recovery action using Gemini when available.
        """
        heuristics = self._calculate_heuristics(root_cause, amount, attempts, clv, is_subscription)

        try:
            from backend.agents.gemini_client import call_gemini
            prompt = f"Recommend recovery action for a failed payment. Root Cause: {root_cause}, Amount: ₹{amount}, Previous Attempts: {attempts}, Customer CLV: ₹{clv}, Subscription: {is_subscription}. Choose one of: RETRY_PAYMENT, SCHEDULE_RETRY, SEND_PAYMENT_LINK, REQUEST_PAYMENT_METHOD_UPDATE, ESCALATE_TO_HUMAN, STOP. Explain why. Output raw JSON only with keys: action, confidence (0.0 to 1.0), reason."
            system_instruction = "You are a Recovery Strategy Agent. Decide the optimal intervention for payment failures. Return ONLY a valid JSON object. Do not include markdown code block formats."
            
            llm_text = call_gemini(prompt, system_instruction)
            if llm_text:
                clean_text = llm_text.strip()
                if clean_text.startswith("```"):
                    lines = clean_text.split("\n")
                    clean_text = "\n".join(lines[1:-1]) if lines[0].startswith("```") else clean_text
                
                if clean_text.startswith("json"):
                    clean_text = clean_text[4:].strip()
                
                parsed = json.loads(clean_text)
                
                act = parsed.get("action", heuristics["action"]).upper()
                valid_actions = ["RETRY_PAYMENT", "SCHEDULE_RETRY", "SEND_PAYMENT_LINK", "REQUEST_PAYMENT_METHOD_UPDATE", "ESCALATE_TO_HUMAN", "STOP"]
                if act not in valid_actions:
                    act = heuristics["action"]

                return {
                    "action": act,
                    "confidence": float(parsed.get("confidence", heuristics["confidence"])),
                    "reason": parsed.get("reason", heuristics["reason"])
                }
        except Exception as e:
            if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
                raise RuntimeError(f"StrategyAgent Gemini API Error: {e}")
            logger.warning(f"Gemini not configured or failed. Using heuristics fallback: {e}")

        return heuristics
