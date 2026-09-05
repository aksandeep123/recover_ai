import logging
from datetime import datetime, timedelta
from backend.config import settings

logger = logging.getLogger(__name__)

class PolicyEngine:
    def __init__(self):
        self.max_retries = settings.MAX_RETRIES
        self.max_window_hours = settings.MAX_RECOVERY_WINDOW_HOURS
        self.high_value_threshold = settings.HIGH_VALUE_THRESHOLD_INR

    def check_policy(self, action: str, amount: float, attempts: int, opt_out: bool, 
                     is_fraud: bool, is_disputed: bool, case_created_at: datetime, 
                     previous_actions: list) -> dict:
        """
        Enforces deterministic rules on top of agent recommendations.
        Returns:
            dict: {
                "allowed": bool,
                "action": str (modified or original),
                "reason": str,
                "status": str (APPROVED, BLOCKED, WAITING_APPROVAL, STOPPED)
            }
        """
        # Rule 1: Customer has explicitly opted out of communication
        if opt_out and action in ["SEND_EMAIL", "SEND_SMS", "SEND_WHATSAPP", "SEND_PAYMENT_LINK", "REQUEST_PAYMENT_METHOD_UPDATE"]:
            return {
                "allowed": False,
                "action": "STOP",
                "reason": "Policy Block: Customer has opted out of communication notifications.",
                "status": "STOPPED"
            }

        # Rule 2: Fraud threat flag is active
        if is_fraud:
            return {
                "allowed": False,
                "action": "ESCALATE_TO_HUMAN",
                "reason": "Policy Guardrail: Suspicious/Fraud-suspected transaction. Automatic recovery blocked. Escalate to Risk Desk.",
                "status": "ESCALATED"
            }

        # Rule 3: Payment is disputed (chargeback etc)
        if is_disputed:
            return {
                "allowed": False,
                "action": "STOP",
                "reason": "Policy Guardrail: Transaction is marked as disputed/chargeback. Stop all recovery operations.",
                "status": "STOPPED"
            }

        # Rule 4: Case exceeds recovery window (48 hours)
        case_age_hours = (datetime.utcnow() - case_created_at).total_seconds() / 3600.0
        if case_age_hours > self.max_window_hours:
            return {
                "allowed": False,
                "action": "STOP",
                "reason": f"Policy Guardrail: Recovery window of {self.max_window_hours} hours expired (Current age: {case_age_hours:.1f}h).",
                "status": "EXPIRED"
            }

        # Rule 5: Retry limit exceeded
        if attempts >= self.max_retries and action in ["RETRY_PAYMENT", "SCHEDULE_RETRY"]:
            return {
                "allowed": False,
                "action": "STOP",
                "reason": f"Policy Guardrail: Max retry attempts ({self.max_retries}) exceeded.",
                "status": "STOPPED"
            }

        # Rule 6: Duplicate action check (don't send same link twice within 1 hour)
        duplicate_actions = [
            a for a in previous_actions 
            if a["action_type"] == action and a["status"] in ["SUCCESS", "PENDING"]
        ]
        if duplicate_actions:
            # Check if last similar action was within 1 hour
            last_action_time = max([datetime.strptime(a["created_at"], "%Y-%m-%d %H:%M:%S") if isinstance(a["created_at"], str) else a["created_at"] for a in duplicate_actions])
            if (datetime.utcnow() - last_action_time).total_seconds() < 3600:
                return {
                    "allowed": False,
                    "action": "STOP",
                    "reason": f"Policy Guardrail: Duplicate action prevention. Action '{action}' was recently executed.",
                    "status": "STOPPED"
                }

        # Rule 7: High-value transaction requires human approval
        if amount >= self.high_value_threshold:
            # If the action has already been manually approved, allow it
            already_approved = False
            for act in previous_actions:
                if act["action_type"] == action and act["status"] == "APPROVED":
                    already_approved = True
                    break
            
            if not already_approved and action not in ["ESCALATE_TO_HUMAN", "STOP"]:
                return {
                    "allowed": False,
                    "action": "WAITING_APPROVAL",
                    "reason": f"Policy Guardrail: High-value payment (₹{amount} >= threshold ₹{self.high_value_threshold}) requires human verification.",
                    "status": "WAITING_APPROVAL"
                }

        return {
            "allowed": True,
            "action": action,
            "reason": "All deterministic policy guardrails passed.",
            "status": "APPROVED"
        }
