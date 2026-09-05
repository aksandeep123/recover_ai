import json
import logging
from datetime import datetime
from backend.config import settings

logger = logging.getLogger(__name__)

class EvaluationAgent:
    def __init__(self):
        pass

    def _generate_llm_summary(self, case_id: str, action_type: str, status: str, details: str) -> str:
        """Calls Gemini to compile an intelligent evaluation summary."""
        try:
            from backend.agents.gemini_client import call_gemini
            prompt = (
                f"Compile a short recovery evaluation log for Case {case_id}. "
                f"Action Executed: {action_type}, Status: {status}, Gateway Output: {details}. "
                f"Write a 1-sentence analytical log explaining the result and what next state is expected."
            )
            system_instruction = "You are a Recovery Evaluation Agent. Summarize gateway outcomes. Output the log text ONLY. No quotes."
            
            summary = call_gemini(prompt, system_instruction)
            if summary:
                text = summary.strip()
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                return text
        except Exception as e:
            if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip() and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
                raise RuntimeError(f"EvaluationAgent Gemini API Error: {e}")
            logger.warning(f"Gemini not configured or failed for evaluation log. Fallback to templates: {e}")
        return None

    def evaluate(self, case_id: str, action_type: str, action_result: dict, case_created_at: datetime) -> dict:
        """
        Evaluates the results of an executed action and decides the next step using Gemini for summaries.
        """
        status = action_result.get("status")
        
        # 1. Action Succeeded (e.g. Payment Retry was successful)
        if status == "SUCCESS":
            recovered_amount = action_result.get("amount_charged", 0.0)
            now = datetime.utcnow()
            time_diff = now - case_created_at
            recovery_time_minutes = round(time_diff.total_seconds() / 60.0, 2)

            default_msg = f"Action {action_type} succeeded! Recovered ₹{recovered_amount:.2f} in {recovery_time_minutes:.1f} minutes."
            llm_msg = self._generate_llm_summary(case_id, action_type, "SUCCESS", f"Recovered ₹{recovered_amount:.2f} in {recovery_time_minutes:.1f}m")
            
            return {
                "success": True,
                "next_status": "RECOVERED",
                "recovered_amount": recovered_amount,
                "recovery_time_minutes": recovery_time_minutes,
                "message": llm_msg or default_msg
            }

        # 2. Action failed (e.g. Retry failed)
        elif status == "FAILED":
            fail_reason = action_result.get("failure_reason", "UNKNOWN_ERROR")
            default_msg = f"Action {action_type} failed due to: {fail_reason}. Case sent back for diagnostic analysis."
            llm_msg = self._generate_llm_summary(case_id, action_type, "FAILED", f"Declined: {fail_reason}")

            return {
                "success": False,
                "next_status": "ANALYZING", 
                "error_reason": fail_reason,
                "message": llm_msg or default_msg
            }

        # 3. Scheduled Retry
        elif status == "SCHEDULED":
            default_msg = f"Action scheduled successfully. Running automatic retry at {action_result.get('scheduled_time')}."
            llm_msg = self._generate_llm_summary(case_id, action_type, "SCHEDULED", f"Job scheduled at {action_result.get('scheduled_time')}")

            return {
                "success": True,
                "next_status": "ACTION_EXECUTED",
                "message": llm_msg or default_msg
            }

        # 4. Payment Link Created or Card Update Request Generated
        elif status in ["CREATED", "LINK_GENERATED"]:
            default_msg = "Recovery communications dispatched. Waiting for customer interaction with recovery link."
            llm_msg = self._generate_llm_summary(case_id, action_type, "COMMUNICATIONS_SENT", "Link created, SMS/Email sent")

            return {
                "success": True,
                "next_status": "ACTION_EXECUTED",
                "message": llm_msg or default_msg
            }

        # 5. Case escalated
        elif status == "ESCALATED":
            default_msg = "Case escalated to Human Approval / VIP Desk."
            llm_msg = self._generate_llm_summary(case_id, action_type, "ESCALATED", action_result.get("notes", "VIP Hold"))

            return {
                "success": True,
                "next_status": "ESCALATED",
                "message": llm_msg or default_msg
            }

        # 6. Stop
        elif status == "STOPPED":
            reason_str = action_result.get('stopped_reason', 'Policy termination')
            default_msg = f"Recovery operations halted: {reason_str}."
            llm_msg = self._generate_llm_summary(case_id, action_type, "STOPPED", reason_str)

            return {
                "success": True,
                "next_status": "STOPPED",
                "message": llm_msg or default_msg
            }

        # Catch-all
        return {
            "success": False,
            "next_status": "ANALYZING",
            "message": "Unrecognized action status. Recalculating strategy."
        }
