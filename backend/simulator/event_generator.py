import random
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.db.models import Customer, Transaction, Subscription, RecoveryCase, PaymentEvent
from backend.agents.orchestrator import RecoverAIOrchestrator

logger = logging.getLogger(__name__)

class EventSimulator:
    def __init__(self, db: Session):
        self.db = db
        self.orchestrator = RecoverAIOrchestrator(db)

    def trigger_payment_failed_event(self, amount: float = None, customer_id: str = None, failure_reason: str = None) -> RecoveryCase:
        """
        Triggers a single simulated payment failure event.
        """
        # Find a random customer if not provided
        if not customer_id:
            cust = self.db.query(Customer).order_by(Customer.id).offset(
                random.randint(0, self.db.query(Customer).count() - 1)
            ).first()
            customer_id = cust.id
        else:
            cust = self.db.query(Customer).filter(Customer.id == customer_id).first()

        if not amount:
            # Set a random amount based on CLV
            base = 199.0 if cust.clv < 5000 else (3999.0 if cust.clv < 50000 else 75000.0)
            amount = round(base + random.uniform(-base * 0.2, base * 0.4), 2)

        # Generate a mock failed transaction
        txn_id = f"TXN_SIM_{datetime.utcnow().strftime('%m%d%H%M')}_{random.randint(10,99)}"
        
        if not failure_reason:
            fail_reasons = ["INSUFFICIENT_FUNDS", "BANK_DECLINE", "TEMPORARY_BANK_ISSUE", "TIMEOUT", "AUTHENTICATION_FAILURE", "EXPIRED_PAYMENT_METHOD"]
            fail_reason = random.choices(fail_reasons, weights=[0.40, 0.25, 0.15, 0.10, 0.05, 0.05], k=1)[0]
            
            # High value test or regular
            if amount > 20000.0:
                # Maybe bank decline or timeout
                fail_reason = random.choice(["BANK_DECLINE", "TIMEOUT", "INSUFFICIENT_FUNDS"])

            # 5% chance of suspected fraud for safety testing
            if random.random() < 0.05:
                fail_reason = "FRAUD_SUSPECTED"
        else:
            fail_reason = failure_reason

        txn = Transaction(
            id=txn_id,
            customer_id=customer_id,
            merchant_id="MERCH_SAAS_2",
            amount=amount,
            currency="INR",
            status="FAILED",
            payment_method=random.choice(["CARD", "UPI", "NETBANKING"]),
            failure_reason=fail_reason,
            created_at=datetime.utcnow()
        )
        self.db.add(txn)
        self.db.commit()

        # Trigger recovery loop via webhook orchestrator
        payload = {
            "transaction_id": txn_id,
            "customer_id": customer_id,
            "amount": amount,
            "failure_reason": fail_reason
        }
        
        case = self.orchestrator.process_failed_payment_event("PAYMENT_FAILED", payload)
        return case

    def run_batch_simulation(self, count: int = 100) -> dict:
        """
        Runs a simulation of multiple events. For each event, we run the orchestration loop.
        To make it realistic, we also simulate some customer responses (e.g. paying payment links after some delays).
        """
        cases_created = 0
        recovered_count = 0
        escalated_count = 0
        stopped_count = 0
        total_recovered_revenue = 0.0

        # Run multiple loops
        for _ in range(count):
            try:
                # Trigger a failure event
                case = self.trigger_payment_failed_event()
                cases_created += 1

                # Simulate customer behavior on links or retries:
                # For non-escalated, non-stopped cases, let's simulate the outcome:
                # Retries have a built-in probability of success.
                # Payment links: let's say 40% of customers click and pay.
                # Subcard update request: 30% update card details.
                self.db.refresh(case)

                if case.status == "ACTION_EXECUTED":
                    # Simulate payment success after retry/link
                    # Determine strategy recommended
                    rec = case.strategy_recommendation
                    
                    # 50% chance customer completes recovery action successfully
                    if rec in ["SEND_PAYMENT_LINK", "REQUEST_PAYMENT_METHOD_UPDATE"] and random.random() < 0.45:
                        # Mark recovered
                        case.status = "RECOVERED"
                        case.recovered_at = datetime.utcnow() + timedelta(minutes=random.randint(5, 60))
                        case.recovered_amount = case.amount
                        case.revenue_at_risk = 0.0
                        case.recovery_time_minutes = round(random.uniform(5.0, 60.0), 2)
                        
                        # Add Audit log
                        self.db.add(AuditLog(
                            case_id=case.id,
                            agent="EvaluationAgent",
                            action="SIMULATE_CUSTOMER_PAYMENT",
                            decision="RECOVERED",
                            reason=f"Customer completed payment link checkout of ₹{case.amount:.2f}.",
                            created_at=datetime.utcnow()
                        ))
                        recovered_count += 1
                        total_recovered_revenue += case.amount

                    elif rec == "SCHEDULE_RETRY" and random.random() < 0.60:
                        # Scheduled retry succeeded
                        case.status = "RECOVERED"
                        case.recovered_at = datetime.utcnow() + timedelta(minutes=30)
                        case.recovered_amount = case.amount
                        case.revenue_at_risk = 0.0
                        case.recovery_time_minutes = 30.0
                        
                        self.db.add(AuditLog(
                            case_id=case.id,
                            agent="EvaluationAgent",
                            action="SIMULATE_SCHEDULED_RETRY",
                            decision="RECOVERED",
                            reason=f"Scheduled gateway retry of ₹{case.amount:.2f} completed successfully.",
                            created_at=datetime.utcnow()
                        ))
                        recovered_count += 1
                        total_recovered_revenue += case.amount

                elif case.status == "ESCALATED":
                    escalated_count += 1
                elif case.status in ["STOPPED", "EXPIRED"]:
                    stopped_count += 1

                self.db.commit()

            except Exception as e:
                logger.error(f"Error during simulator batch event: {e}")
                self.db.rollback()

        return {
            "cases_processed": cases_created,
            "recovered": recovered_count,
            "escalated": escalated_count,
            "stopped": stopped_count,
            "revenue_recovered": round(total_recovered_revenue, 2)
        }
