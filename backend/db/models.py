from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.db.session import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    clv = Column(Float, default=0.0)  # Customer Lifetime Value
    preferred_channel = Column(String, default="EMAIL")  # EMAIL, SMS, WHATSAPP
    opt_out = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="customer")
    subscriptions = relationship("Subscription", back_populates="customer")
    cases = relationship("RecoveryCase", back_populates="customer")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    merchant_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    status = Column(String, nullable=False)  # SUCCESS, FAILED, PENDING, REFUNDED
    payment_method = Column(String, nullable=False)  # CARD, UPI, NETBANKING, WALLET
    failure_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="transactions")
    cases = relationship("RecoveryCase", back_populates="transaction")
    payment_events = relationship("PaymentEvent", back_populates="transaction")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    status = Column(String, nullable=False)  # ACTIVE, PAST_DUE, CANCELLED
    mrr = Column(Float, nullable=False)  # Monthly Recurring Revenue
    next_billing_at = Column(DateTime, nullable=False)
    failures_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="subscriptions")
    cases = relationship("RecoveryCase", back_populates="subscription")

class RecoveryCase(Base):
    __tablename__ = "recovery_cases"

    id = Column(String, primary_key=True, index=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True)
    subscription_id = Column(String, ForeignKey("subscriptions.id"), nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # AT_RISK, ANALYZING, ACTION_RECOMMENDED, WAITING_APPROVAL, ACTION_EXECUTED, RECOVERED, ESCALATED, STOPPED, EXPIRED
    risk_score = Column(Integer, default=0)
    revenue_at_risk = Column(Float, default=0.0)
    failure_reason = Column(String, nullable=False)
    root_cause = Column(String, nullable=True)  # insufficient_funds, bank_decline, timeout, etc.
    root_cause_explanation = Column(Text, nullable=True)
    strategy_recommendation = Column(String, nullable=True)  # RETRY_PAYMENT, SEND_PAYMENT_LINK, etc.
    strategy_confidence = Column(Float, nullable=True)
    strategy_reason = Column(Text, nullable=True)
    attempts_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    recovered_at = Column(DateTime, nullable=True)
    recovery_time_minutes = Column(Float, nullable=True)
    recovered_amount = Column(Float, default=0.0)

    customer = relationship("Customer", back_populates="cases")
    transaction = relationship("Transaction", back_populates="cases")
    subscription = relationship("Subscription", back_populates="cases")
    actions = relationship("RecoveryAction", back_populates="case")
    notifications = relationship("NotificationLog", back_populates="case")
    audit_logs = relationship("AuditLog", back_populates="case")
    payment_events = relationship("PaymentEvent", back_populates="case")

class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True)
    event_type = Column(String, nullable=False)  # PAYMENT_FAILED, SUBSCRIPTION_PAYMENT_FAILED, CHECKOUT_ABANDONED, PAYMENT_RETRY_FAILED, PAYMENT_SUCCESS
    payload = Column(Text, nullable=True)  # JSON representation
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("RecoveryCase", back_populates="payment_events")
    transaction = relationship("Transaction", back_populates="payment_events")

class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=False)
    action_type = Column(String, nullable=False)  # RETRY_PAYMENT, SEND_PAYMENT_LINK, etc.
    status = Column(String, nullable=False)  # PENDING, APPROVED, REJECTED, EXECUTING, SUCCESS, FAILED
    payload = Column(Text, nullable=True)  # JSON params
    result = Column(Text, nullable=True)  # JSON output from mock APIs
    execution_error = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)  # AI_SYSTEM, HUMAN_USER
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("RecoveryCase", back_populates="actions")

class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(String, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=False)
    channel = Column(String, nullable=False)  # EMAIL, SMS, WHATSAPP
    recipient = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String, default="English")  # English, Hinglish
    status = Column(String, nullable=False)  # SENT, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("RecoveryCase", back_populates="notifications")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String, ForeignKey("recovery_cases.id"), nullable=True)
    agent = Column(String, nullable=False)  # RiskAgent, RootCauseAgent, etc.
    action = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    policy_check = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("RecoveryCase", back_populates="audit_logs")
