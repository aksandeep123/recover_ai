import json
import uuid
import logging
from datetime import datetime, timedelta
from backend.config import settings

logger = logging.getLogger(__name__)

class ExecutionAgent:
    def __init__(self):
        pass

    def retry_payment(self, transaction_id: str, amount: float, success_probability: float = 0.65) -> dict:
        """
        Simulates an immediate API call to the payment gateway to retry a card or UPI payment.
        """
        import random
        # Seed random based on timestamp to simulate real network randomness
        is_success = random.random() < success_probability
        
        ref_id = f"PAY_REF_{uuid.uuid4().hex[:8].upper()}"
        if is_success:
            return {
                "status": "SUCCESS",
                "payment_reference": ref_id,
                "amount_charged": amount,
                "completed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "gateway": "Razorpay Simulated Route"
            }
        else:
            # Random decline code
            decline_reasons = ["INSUFFICIENT_FUNDS", "BANK_DECLINE", "TEMPORARY_BANK_ISSUE", "TIMEOUT"]
            reason = random.choice(decline_reasons)
            return {
                "status": "FAILED",
                "payment_reference": ref_id,
                "failure_reason": reason,
                "error_code": "GATEWAY_ERR_503",
                "completed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            }

    def schedule_retry(self, case_id: str, delay_minutes: int = 30) -> dict:
        """
        Simulates scheduling a payment retry task in the job queue.
        """
        scheduled_time = datetime.utcnow() + timedelta(minutes=delay_minutes)
        return {
            "status": "SCHEDULED",
            "scheduled_time": scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
            "delay_minutes": delay_minutes,
            "job_id": f"JOB_{uuid.uuid4().hex[:6].upper()}"
        }

    def create_payment_link(self, case_id: str, amount: float) -> dict:
        """
        Creates a Razorpay-style payment link. Supports real Razorpay Test API if credentials are provided.
        """
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            try:
                import razorpay
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                
                # Razorpay expects amount in paise (₹1 = 100 paise)
                amount_in_paise = int(amount * 100)
                
                link_data = {
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "accept_partial": False,
                    "description": f"RecoverAI Recovery Link for Case {case_id}",
                    "callback_url": f"http://127.0.0.1:3000/", # Redirect back to React frontend
                    "callback_method": "get"
                }
                
                logger.info(f"Connecting to real Razorpay client to generate test link...")
                payment_link = client.payment_link.create(link_data)
                
                return {
                    "status": "CREATED",
                    "payment_link_id": payment_link.get("id"),
                    "short_url": payment_link.get("short_url"),
                    "amount": amount,
                    "expires_at": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
                    "provider": "Razorpay Test Mode"
                }
            except Exception as e:
                logger.error(f"Error executing real Razorpay link creation, falling back to simulation: {e}")

        # Fallback to simulation
        short_url = f"https://rzp.io/l/rec_{case_id}"
        return {
            "status": "CREATED",
            "payment_link_id": f"plink_{uuid.uuid4().hex[:10]}",
            "short_url": short_url,
            "amount": amount,
            "expires_at": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "provider": "Simulated Gateway"
        }

    def send_notification(self, channel: str, recipient: str, message: str) -> dict:
        """
        Simulates sending a notification (Email, SMS, or WhatsApp) via gateway.
        """
        logger.info(f"Notification Sent [{channel}] to {recipient}: '{message}'")
        return {
            "status": "SENT",
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
            "delivered_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "provider": "RecoverAI Comms Hub"
        }

    def update_payment_method_request(self, subscription_id: str) -> dict:
        """
        Simulates generating a secure link for updating payment card details.
        """
        update_url = f"https://recoverai.net/update-card/sub_{subscription_id}"
        return {
            "status": "LINK_GENERATED",
            "update_url": update_url,
            "token": uuid.uuid4().hex
        }

    def escalate_case(self, case_id: str, reason: str) -> dict:
        """
        Escalates the case to human customer support desk.
        """
        return {
            "status": "ESCALATED",
            "queue_name": "VIP_RECOVERY_QUEUE",
            "agent_assigned": None,
            "escalated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "notes": reason
        }

    def stop_recovery(self, case_id: str, reason: str) -> dict:
        """
        Stops the recovery loop for the case.
        """
        return {
            "status": "STOPPED",
            "stopped_reason": reason,
            "stopped_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
