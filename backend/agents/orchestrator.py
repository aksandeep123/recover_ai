import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.db.models import RecoveryCase, Customer, Transaction, Subscription, RecoveryAction, NotificationLog, AuditLog, PaymentEvent
from backend.agents.risk import RiskAgent
from backend.agents.root_cause import RootCauseAgent
from backend.agents.strategy import StrategyAgent
from backend.agents.communication import CommunicationAgent
from backend.agents.execution import ExecutionAgent
from backend.agents.evaluation import EvaluationAgent
from backend.policies.engine import PolicyEngine

logger = logging.getLogger(__name__)

class RecoverAIOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.risk_agent = RiskAgent()
        self.root_cause_agent = RootCauseAgent()
        self.strategy_agent = StrategyAgent()
        self.comms_agent = CommunicationAgent()
        self.execution_agent = ExecutionAgent()
        self.evaluation_agent = EvaluationAgent()
        self.policy_engine = PolicyEngine()

    def process_failed_payment_event(self, event_type: str, payload_data: dict) -> RecoveryCase:
        """
        Closed-loop entrypoint when a failed payment gateway webhook event is received.
        Creates a new case and triggers the autonomous recovery loop.
        """
        # 1. Parse payload details
        txn_id = payload_data.get("transaction_id")
        sub_id = payload_data.get("subscription_id")
        amount = payload_data.get("amount", 0.0)
        failure_reason = payload_data.get("failure_reason", "UNKNOWN_ERROR")
        customer_id = payload_data.get("customer_id")

        if not customer_id and txn_id:
            # Lookup customer from transaction
            txn = self.db.query(Transaction).filter(Transaction.id == txn_id).first()
            if txn:
                customer_id = txn.customer_id
                amount = txn.amount
                failure_reason = txn.failure_reason or failure_reason

        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer {customer_id} not found in database.")

        # Check if an active recovery case already exists for this transaction
        existing_case = None
        if txn_id:
            existing_case = self.db.query(RecoveryCase).filter(
                RecoveryCase.transaction_id == txn_id,
                RecoveryCase.status.in_(["AT_RISK", "ANALYZING", "ACTION_RECOMMENDED", "WAITING_APPROVAL", "ACTION_EXECUTED"])
            ).first()
        elif sub_id:
            existing_case = self.db.query(RecoveryCase).filter(
                RecoveryCase.subscription_id == sub_id,
                RecoveryCase.status.in_(["AT_RISK", "ANALYZING", "ACTION_RECOMMENDED", "WAITING_APPROVAL", "ACTION_EXECUTED"])
            ).first()

        if existing_case:
            logger.info(f"Using existing active recovery case {existing_case.id}")
            case = existing_case
        else:
            # Create a brand new case
            case_id = f"CASE_AUTO_{datetime.utcnow().strftime('%m%d')}_{uuid_short()}"
            case = RecoveryCase(
                id=case_id,
                customer_id=customer.id,
                transaction_id=txn_id,
                subscription_id=sub_id,
                amount=amount,
                status="AT_RISK",
                failure_reason=failure_reason,
                attempts_count=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(case)
            self.db.commit()
            self.db.refresh(case)

            # Store the PaymentEvent
            evt = PaymentEvent(
                id=f"EVT_{case.id}_{uuid_short()}",
                case_id=case.id,
                transaction_id=txn_id,
                event_type=event_type,
                payload=json.dumps(payload_data),
                created_at=datetime.utcnow()
            )
            self.db.add(evt)
            self.db.commit()

        # Run loop
        return self.run_agent_workflow(case)

    def run_agent_workflow(self, case: RecoveryCase) -> RecoveryCase:
        """
        Executes the main agent cycle: Risk -> Root Cause -> Strategy -> Policy -> [Execute / Pause]
        """
        case.status = "ANALYZING"
        self.db.commit()

        customer = case.customer
        previous_failures = self.db.query(Transaction).filter(
            Transaction.customer_id == customer.id,
            Transaction.status == "FAILED"
        ).count()

        # Step 1: Risk Agent
        risk_result = self.risk_agent.analyze(
            amount=case.amount,
            customer_clv=customer.clv,
            previous_failures=previous_failures,
            opt_out=customer.opt_out
        )
        case.risk_score = risk_result["risk_score"]
        case.revenue_at_risk = risk_result["revenue_at_risk"]
        
        self.db.add(AuditLog(
            case_id=case.id,
            agent="RevenueRiskAgent",
            action="ANALYZE_RISK",
            decision=f"RISK_SCORE={case.risk_score}",
            reason=risk_result["explanation"],
            created_at=datetime.utcnow()
        ))

        # Step 2: Root Cause Agent
        rc_result = self.root_cause_agent.diagnose(case.failure_reason)
        case.root_cause = rc_result["root_cause"]
        case.root_cause_explanation = rc_result["explanation"]

        self.db.add(AuditLog(
            case_id=case.id,
            agent="RootCauseAgent",
            action="DIAGNOSE",
            decision=case.root_cause,
            reason=case.root_cause_explanation,
            created_at=datetime.utcnow()
        ))

        # Step 3: Strategy Agent
        is_sub = case.subscription_id is not None
        strat_result = self.strategy_agent.recommend(
            root_cause=case.root_cause,
            amount=case.amount,
            attempts=case.attempts_count,
            clv=customer.clv,
            is_subscription=is_sub
        )
        case.strategy_recommendation = strat_result["action"]
        case.strategy_confidence = strat_result["confidence"]
        case.strategy_reason = strat_result["reason"]

        self.db.add(AuditLog(
            case_id=case.id,
            agent="RecoveryStrategyAgent",
            action="RECOMMEND",
            decision=case.strategy_recommendation,
            reason=case.strategy_reason,
            confidence=case.strategy_confidence,
            created_at=datetime.utcnow()
        ))
        self.db.commit()

        # Step 4: Policy Engine Check
        previous_actions_query = self.db.query(RecoveryAction).filter(RecoveryAction.case_id == case.id).all()
        previous_actions = [
            {"action_type": a.action_type, "status": a.status, "created_at": a.created_at} 
            for a in previous_actions_query
        ]
        
        # Suspected fraud flag (for testing)
        is_fraud = case.failure_reason == "FRAUD_SUSPECTED" or case.root_cause == "FRAUD_SUSPECTED"
        is_disputed = case.failure_reason == "DISPUTED"

        policy_result = self.policy_engine.check_policy(
            action=case.strategy_recommendation,
            amount=case.amount,
            attempts=case.attempts_count,
            opt_out=customer.opt_out,
            is_fraud=is_fraud,
            is_disputed=is_disputed,
            case_created_at=case.created_at,
            previous_actions=previous_actions
        )

        # Log policy check
        self.db.add(AuditLog(
            case_id=case.id,
            agent="PolicyEngine",
            action="CHECK_GUARDRAILS",
            decision=policy_result["status"],
            reason=policy_result["reason"],
            policy_check=f"Allowed={policy_result['allowed']}; NextAction={policy_result['action']}",
            created_at=datetime.utcnow()
        ))

        # Handle Policy Decision
        next_action = policy_result["action"]
        
        if next_action == "WAITING_APPROVAL":
            case.status = "WAITING_APPROVAL"
            self.db.commit()
            return case
            
        elif next_action == "ESCALATE_TO_HUMAN":
            case.status = "ESCALATED"
            self.db.commit()
            # Perform escalation
            self.execute_action(case, "ESCALATE_TO_HUMAN", approved_by="AI_SYSTEM")
            return case
            
        elif next_action == "STOP":
            case.status = policy_result.get("status", "STOPPED")
            case.revenue_at_risk = 0.0
            self.db.commit()
            # Perform stop action
            self.execute_action(case, "STOP", approved_by="AI_SYSTEM", stop_reason=policy_result["reason"])
            return case
            
        elif next_action == "EXPIRED":
            case.status = "EXPIRED"
            case.revenue_at_risk = 0.0
            self.db.commit()
            return case

        # Action is APPROVED for execution!
        case.status = "ACTION_EXECUTED"
        self.db.commit()
        
        # Step 5: Execute and Evaluate Action
        self.execute_action(case, next_action, approved_by="AI_SYSTEM")
        return case

    def execute_action(self, case: RecoveryCase, action_type: str, approved_by: str = "AI_SYSTEM", stop_reason: str = None) -> RecoveryAction:
        """
        Invokes mock API integrations to perform action, then evaluates result.
        """
        customer = case.customer
        idemp_key = f"IDEMP_{case.id}_{action_type.upper()}_{case.attempts_count}"

        # Check for idempotency
        existing_action = self.db.query(RecoveryAction).filter(RecoveryAction.idempotency_key == idemp_key).first()
        if existing_action:
            self.db.add(AuditLog(
                case_id=case.id,
                agent="ExecutionAgent",
                action="EXECUTE",
                decision="REJECTED_IDEMPOTENT",
                reason=f"Action {action_type} with key {idemp_key} already processed.",
                created_at=datetime.utcnow()
            ))
            self.db.commit()
            return existing_action

        # Create action in database
        action_id = f"ACT_{uuid_short()}"
        action = RecoveryAction(
            id=action_id,
            case_id=case.id,
            action_type=action_type,
            status="EXECUTING",
            payload=json.dumps({"recipient": customer.email, "amount": case.amount}),
            approved_by=approved_by,
            idempotency_key=idemp_key,
            created_at=datetime.utcnow()
        )
        self.db.add(action)
        self.db.commit()

        # Simulate execution
        result = {}
        if action_type == "RETRY_PAYMENT":
            case.attempts_count += 1
            result = self.execution_agent.retry_payment(case.transaction_id or "TXN_MOCK", case.amount)
            
        elif action_type == "SCHEDULE_RETRY":
            case.attempts_count += 1
            result = self.execution_agent.schedule_retry(case.id)
            
        elif action_type == "SEND_PAYMENT_LINK":
            result = self.execution_agent.create_payment_link(case.id, case.amount)
            # Dispatch communications
            msg = self.comms_agent.generate_message(customer.name, case.amount, case.root_cause, customer.preferred_channel, case.id)
            self.execution_agent.send_notification(customer.preferred_channel, customer.email if customer.preferred_channel == "EMAIL" else customer.phone, msg)
            
            # Save Notification Log
            self.db.add(NotificationLog(
                id=f"NOT_{uuid_short()}",
                case_id=case.id,
                channel=customer.preferred_channel,
                recipient=customer.email if customer.preferred_channel == "EMAIL" else customer.phone,
                content=msg,
                language="English", # Default template, Hinglish generated inside comms agent if required
                status="SENT",
                created_at=datetime.utcnow()
            ))
            
        elif action_type == "REQUEST_PAYMENT_METHOD_UPDATE":
            result = self.execution_agent.update_payment_method_request(case.subscription_id or "SUB_MOCK")
            msg = self.comms_agent.generate_message(customer.name, case.amount, case.root_cause, customer.preferred_channel, case.id)
            self.execution_agent.send_notification(customer.preferred_channel, customer.email if customer.preferred_channel == "EMAIL" else customer.phone, msg)

            self.db.add(NotificationLog(
                id=f"NOT_{uuid_short()}",
                case_id=case.id,
                channel=customer.preferred_channel,
                recipient=customer.email if customer.preferred_channel == "EMAIL" else customer.phone,
                content=msg,
                language="English",
                status="SENT",
                created_at=datetime.utcnow()
            ))
            
        elif action_type == "ESCALATE_TO_HUMAN":
            result = self.execution_agent.escalate_case(case.id, case.strategy_reason or "Escalation requested")
            
        elif action_type == "STOP":
            result = self.execution_agent.stop_recovery(case.id, stop_reason or "Stopped by strategy/policy")

        # Save action execution status
        action.status = result.get("status", "SUCCESS")
        action.result = json.dumps(result)
        self.db.commit()

        # Step 6: Evaluate Outcome
        eval_result = self.evaluation_agent.evaluate(case.id, action_type, result, case.created_at)
        
        # Update case based on evaluation
        case.status = eval_result["next_status"]
        if eval_result.get("recovered_amount"):
            case.recovered_at = datetime.utcnow()
            case.recovered_amount = eval_result["recovered_amount"]
            case.revenue_at_risk = 0.0
            case.recovery_time_minutes = eval_result["recovery_time_minutes"]

            # If there was an associated subscription, mark subscription ACTIVE again
            if case.subscription_id:
                sub = self.db.query(Subscription).filter(Subscription.id == case.subscription_id).first()
                if sub:
                    sub.status = "ACTIVE"
                    sub.failures_count = 0
            
            # If there was a transaction, we can update it to SUCCESS
            if case.transaction_id:
                txn = self.db.query(Transaction).filter(Transaction.id == case.transaction_id).first()
                if txn:
                    txn.status = "SUCCESS"

        self.db.add(AuditLog(
            case_id=case.id,
            agent="EvaluationAgent",
            action="EVALUATE_OUTCOME",
            decision=case.status,
            reason=eval_result["message"],
            created_at=datetime.utcnow()
        ))
        
        self.db.commit()
        return action

# Helper function for quick unique IDs
import uuid
def uuid_short():
    return uuid.uuid4().hex[:6].upper()
