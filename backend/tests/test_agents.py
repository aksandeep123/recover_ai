import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.session import Base
from backend.db.models import Customer, Transaction, Subscription, RecoveryCase, RecoveryAction
from backend.agents.risk import RiskAgent
from backend.agents.root_cause import RootCauseAgent
from backend.agents.strategy import StrategyAgent
from backend.agents.orchestrator import RecoverAIOrchestrator
from backend.policies.engine import PolicyEngine

# --- AGENT AND POLICY ENGINE TESTS ---

def test_risk_agent():
    risk_agent = RiskAgent()
    
    # 1. Low risk transaction
    res1 = risk_agent.analyze(amount=200.0, customer_clv=1000.0, previous_failures=0)
    assert res1["risk_score"] < 40
    
    # 2. High risk transaction (repeated failures)
    res2 = risk_agent.analyze(amount=45000.0, customer_clv=1000.0, previous_failures=3)
    assert res2["risk_score"] >= 80
    assert res2["priority"] in ["HIGH", "CRITICAL"]

    # 3. Customer opt-out check triggers high risk
    res3 = risk_agent.analyze(amount=500.0, customer_clv=5000.0, previous_failures=0, opt_out=True)
    assert res3["risk_score"] == 100

def test_root_cause_agent():
    rc_agent = RootCauseAgent()
    
    # 4. Insufficient funds diagnosis
    res1 = rc_agent.diagnose("CUSTOMER_INSUFFICIENT_BALANCE_LIMIT")
    assert res1["root_cause"] == "insufficient_funds"
    
    # 5. Timeout diagnosis
    res2 = rc_agent.diagnose("GATEWAY_TIMEOUT_RESPONSE_SWITCH")
    assert res2["root_cause"] == "timeout"
    
    # 6. Card expired diagnosis
    res3 = rc_agent.diagnose("CARD_EXPIRED_DECLINE")
    assert res3["root_cause"] == "expired_payment_method"

def test_strategy_agent():
    strat_agent = StrategyAgent()
    
    # 7. Temporary bank issue - RETRY
    res1 = strat_agent.recommend(root_cause="temporary_bank_issue", amount=1500.0, attempts=0, clv=5000.0, is_subscription=False)
    assert res1["action"] == "RETRY_PAYMENT"
    
    # 8. Insufficient funds - SEND PAYMENT LINK
    res2 = strat_agent.recommend(root_cause="insufficient_funds", amount=5000.0, attempts=0, clv=10000.0, is_subscription=False)
    assert res2["action"] == "SEND_PAYMENT_LINK"

    # 9. High value transaction - ESCALATE TO HUMAN
    res3 = strat_agent.recommend(root_cause="temporary_bank_issue", amount=25000.0, attempts=0, clv=5000.0, is_subscription=False)
    assert res3["action"] == "ESCALATE_TO_HUMAN"

    # 10. Max retries exceeded - STOP
    res4 = strat_agent.recommend(root_cause="temporary_bank_issue", amount=1500.0, attempts=2, clv=5000.0, is_subscription=False)
    assert res4["action"] == "STOP"

def test_policy_engine_guardrails():
    policy = PolicyEngine()
    
    # 11. Customer opt-out check -> Block communication, stop case
    res_opt_out = policy.check_policy(
        action="SEND_PAYMENT_LINK", 
        amount=500.0, 
        attempts=0, 
        opt_out=True, 
        is_fraud=False, 
        is_disputed=False, 
        case_created_at=datetime.utcnow(), 
        previous_actions=[]
    )
    assert res_opt_out["allowed"] is False
    assert res_opt_out["status"] == "STOPPED"
    
    # 12. High-value control check -> WAITING_APPROVAL
    res_high_val = policy.check_policy(
        action="SEND_PAYMENT_LINK", 
        amount=25000.0, 
        attempts=0, 
        opt_out=False, 
        is_fraud=False, 
        is_disputed=False, 
        case_created_at=datetime.utcnow(), 
        previous_actions=[]
    )
    assert res_high_val["allowed"] is False
    assert res_high_val["status"] == "WAITING_APPROVAL"

    # 13. Fraud threat check -> Block retry, escalate to Risk Desk
    res_fraud = policy.check_policy(
        action="RETRY_PAYMENT", 
        amount=2000.0, 
        attempts=0, 
        opt_out=False, 
        is_fraud=True, 
        is_disputed=False, 
        case_created_at=datetime.utcnow(), 
        previous_actions=[]
    )
    assert res_fraud["allowed"] is False
    assert res_fraud["status"] == "ESCALATED"

    # 14. Max Retries check -> Stop
    res_retries = policy.check_policy(
        action="RETRY_PAYMENT", 
        amount=2000.0, 
        attempts=2, 
        opt_out=False, 
        is_fraud=False, 
        is_disputed=False, 
        case_created_at=datetime.utcnow(), 
        previous_actions=[]
    )
    assert res_retries["allowed"] is False
    assert res_retries["status"] == "STOPPED"

    # 15. 48-Hour Recovery Window Expiry -> Expired
    fifty_hours_ago = datetime.utcnow() - timedelta(hours=50)
    res_expiry = policy.check_policy(
        action="RETRY_PAYMENT", 
        amount=2000.0, 
        attempts=1, 
        opt_out=False, 
        is_fraud=False, 
        is_disputed=False, 
        case_created_at=fifty_hours_ago, 
        previous_actions=[]
    )
    assert res_expiry["allowed"] is False
    assert res_expiry["status"] == "EXPIRED"

    # 16. Duplicate Action / Idempotency check -> Block same action within 1 hour
    recent_actions = [
        {"action_type": "SEND_PAYMENT_LINK", "status": "SUCCESS", "created_at": datetime.utcnow() - timedelta(minutes=15)}
    ]
    res_duplicate = policy.check_policy(
        action="SEND_PAYMENT_LINK", 
        amount=2000.0, 
        attempts=1, 
        opt_out=False, 
        is_fraud=False, 
        is_disputed=False, 
        case_created_at=datetime.utcnow() - timedelta(minutes=30), 
        previous_actions=recent_actions
    )
    assert res_duplicate["allowed"] is False
    assert res_duplicate["status"] == "STOPPED"


# --- STATEFUL ORCHESTRATOR & DB INTEGRATION TESTS ---

@pytest.fixture
def db_session():
    """Provides an isolated, in-memory SQLite database for testing database transitions."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def test_orchestrator_recovery_success(db_session):
    # Setup Customer
    cust = Customer(
        id="CUST_T001",
        name="Test Account",
        email="test@example.com",
        phone="+919000000000",
        clv=15000.0,
        preferred_channel="EMAIL",
        opt_out=False
    )
    db_session.add(cust)
    
    # Setup Transaction failed due to timeout
    txn = Transaction(
        id="TXN_T001",
        customer_id="CUST_T001",
        merchant_id="MERCH_SAAS_2",
        amount=5000.0,
        currency="INR",
        status="FAILED",
        payment_method="CARD",
        failure_reason="TIMEOUT_GATEWAY_RESPONSE",
        created_at=datetime.utcnow()
    )
    db_session.add(txn)
    db_session.commit()

    orchestrator = RecoverAIOrchestrator(db_session)
    
    # Mock the ExecutionAgent's retry_payment method inside the orchestrator to force success
    # (So we verify a deterministic 100% recovery path)
    def mock_retry_payment(txn_id, amount, success_probability=1.0):
        return {
            "status": "SUCCESS",
            "payment_reference": "PAY_REF_TEST",
            "amount_charged": amount,
            "completed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    orchestrator.execution_agent.retry_payment = mock_retry_payment

    # Trigger Orchestrator event processing
    payload = {
        "transaction_id": "TXN_T001",
        "customer_id": "CUST_T001",
        "amount": 5000.0,
        "failure_reason": "TIMEOUT_GATEWAY_RESPONSE"
    }
    case = orchestrator.process_failed_payment_event("PAYMENT_FAILED", payload)

    # Assertions
    db_session.refresh(case)
    assert case.status == "RECOVERED"
    assert case.recovered_amount == 5000.0
    assert case.revenue_at_risk == 0.0
    assert case.attempts_count == 1
    assert case.recovered_at is not None
    assert case.recovery_time_minutes is not None

    # Check updated models
    db_txn = db_session.query(Transaction).filter(Transaction.id == "TXN_T001").first()
    assert db_txn.status == "SUCCESS"

    # Verify audit logs were written
    audits = db_session.query(RecoveryCase).filter(RecoveryCase.id == case.id).first().audit_logs
    assert len(audits) >= 4  # Risk analysis, diagnosis, recommendation, evaluation outcomes
