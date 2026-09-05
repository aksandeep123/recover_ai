import json
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class RiskAgent:
    def __init__(self):
        pass

    def _calculate_heuristics(self, amount: float, customer_clv: float, previous_failures: int, opt_out: bool = False) -> dict:
        """Helper to calculate deterministic fallback scores."""
        base_score = 30
        if amount > 10000:
            base_score += 20
        elif amount > 50000:
            base_score += 35
        else:
            base_score += int(amount / 500)

        base_score += (previous_failures * 15)
        clv_discount = min(15, int(customer_clv / 10000))
        risk_score = max(10, min(99, base_score - clv_discount))

        if opt_out:
            risk_score = 100

        if risk_score >= 85:
            priority = "CRITICAL"
        elif risk_score >= 70:
            priority = "HIGH"
        elif risk_score >= 45:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        explanation = f"Base risk score determined by transaction amount of ₹{amount:.2f} and failure count ({previous_failures})."
        if customer_clv > 20000:
            explanation += f" Adjusted down by ₹{customer_clv:.2f} CLV affinity discount."

        return {
            "risk_score": risk_score,
            "revenue_at_risk": amount if not opt_out else 0.0,
            "priority": priority,
            "explanation": explanation
        }

    def analyze(self, amount: float, customer_clv: float, previous_failures: int, opt_out: bool = False) -> dict:
        """
        Calculates risk score (0-100) and priority of recovery using Gemini if available.
        """
        heuristics = self._calculate_heuristics(amount, customer_clv, previous_failures, opt_out)

        try:
            from backend.agents.gemini_client import call_gemini
            prompt = f"Analyze risk for a failed transaction. Amount: ₹{amount}, Customer CLV: ₹{customer_clv}, Previous Failures: {previous_failures}, Opt-out: {opt_out}. Output raw JSON only with keys: risk_score (0-100), priority (LOW/MEDIUM/HIGH/CRITICAL), and explanation."
            system_instruction = "You are a Revenue Risk Agent. Analyze transaction details and customer metrics to score churn risk and priority. Return ONLY a valid JSON object. Do not include markdown code block syntax."
            
            llm_text = call_gemini(prompt, system_instruction)
            if llm_text:
                clean_text = llm_text.strip()
                if clean_text.startswith("```"):
                    lines = clean_text.split("\n")
                    # Remove first and last line of code blocks
                    clean_text = "\n".join(lines[1:-1]) if lines[0].startswith("```") else clean_text
                
                # Check for prepended "json" in code blocks
                if clean_text.startswith("json"):
                    clean_text = clean_text[4:].strip()
                
                parsed = json.loads(clean_text)
                return {
                    "risk_score": int(parsed.get("risk_score", heuristics["risk_score"])),
                    "revenue_at_risk": amount if not opt_out else 0.0,
                    "priority": parsed.get("priority", heuristics["priority"]).upper(),
                    "explanation": parsed.get("explanation", heuristics["explanation"])
                }
        except Exception as e:
            if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
                raise RuntimeError(f"RiskAgent Gemini API Error: {e}")
            logger.warning(f"Gemini not configured or failed. Using heuristics fallback: {e}")

        return heuristics
