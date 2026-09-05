import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class CommunicationAgent:
    def __init__(self):
        pass

    def _generate_heuristics(self, name: str, amount: float, root_cause: str, language: str = "English", case_id: str = "") -> str:
        """Fallback heuristics for notification copy generation."""
        link = f"https://rzp.io/l/rec_{case_id or 'checkout'}"
        
        if language == "Hinglish":
            if root_cause == "insufficient_funds":
                msg = f"Hi {name}, aapka ₹{amount:.2f} ka payment balance ki wajah se fail ho gaya. Kripya is payment link par click karke alternative methods (UPI, Card) se complete karein: {link} - RecoverAI"
            elif root_cause == "expired_payment_method":
                msg = f"Hi {name}, aapka card expired ho chuka hai, jiski wajah se ₹{amount:.2f} ka payment fail hua. Card update karne ya complete karne ke liye click karein: {link} - RecoverAI"
            elif root_cause == "authentication_failure":
                msg = f"Hi {name}, OTP verification na hone se ₹{amount:.2f} payment decline hua. Please yahan click karke retry karein: {link} - RecoverAI"
            elif root_cause == "checkout_abandonment":
                msg = f"Hi {name}, aapki cart mein items pending hain! Click karke ₹{amount:.2f} ka payment complete karein aur order confirm karein: {link} - RecoverAI"
            else:
                msg = f"Hi {name}, aapka ₹{amount:.2f} ka payment fail ho gaya hai. Dobara complete karne ke liye is security-checked link par click karein: {link} - RecoverAI"
        else: # English
            if root_cause == "insufficient_funds":
                msg = f"Hi {name}, your payment of ₹{amount:.2f} was declined due to insufficient funds. You can easily pay via UPI, Netbanking, or another card here: {link} - RecoverAI"
            elif root_cause == "expired_payment_method":
                msg = f"Hi {name}, your card on file has expired, causing the subscription payment of ₹{amount:.2f} to fail. Please update your details here: {link} - RecoverAI"
            elif root_cause == "authentication_failure":
                msg = f"Hi {name}, the payment of ₹{amount:.2f} failed due to a missing or incorrect OTP. Complete your transaction securely here: {link} - RecoverAI"
            elif root_cause == "checkout_abandonment":
                msg = f"Hi {name}, we noticed you didn't finish your checkout. Secure your order of ₹{amount:.2f} by clicking here: {link} - RecoverAI"
            else:
                msg = f"Hi {name}, your transaction of ₹{amount:.2f} could not be completed. Click this link to retry using an alternative payment method: {link} - RecoverAI"

        return msg

    def generate_message(self, name: str, amount: float, root_cause: str, language: str = "English", case_id: str = "") -> str:
        """
        Generates personalized communications in English or Hinglish using Gemini when available.
        """
        heuristics = self._generate_heuristics(name, amount, root_cause, language, case_id)

        try:
            from backend.agents.gemini_client import call_gemini
            link = f"https://rzp.io/l/rec_{case_id or 'checkout'}"
            
            prompt = (
                f"Write a recovery message for customer '{name}' who had a failed payment of ₹{amount:.2f} "
                f"due to '{root_cause}'. The message should include the payment link '{link}'. "
                f"Format the message in {language}. Keep the length under 2 sentences, make it polite, "
                f"reassuring, and secure."
            )
            system_instruction = (
                "You are a Fintech Customer Communication Agent. Write clear, friendly, and non-intrusive messages. "
                "Output the text content of the message ONLY. Do not write introductory text, wrappers, or quotes."
            )
            
            llm_text = call_gemini(prompt, system_instruction)
            if llm_text:
                # Remove quotes if Gemini wraps the response in quotes
                text = llm_text.strip()
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                return text
        except Exception as e:
            if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
                raise RuntimeError(f"CommunicationAgent Gemini API Error: {e}")
            logger.warning(f"Gemini not configured or failed. Using heuristics fallback: {e}")

        return heuristics
