import random
from datetime import datetime, timedelta
from backend.db.session import SessionLocal, engine, Base
from backend.db.models import Customer, Transaction, Subscription, RecoveryCase, RecoveryAction, NotificationLog, AuditLog, PaymentEvent

# Seed generator for reproducibility
random.seed(42)

def seed_db():
    print("Recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Seeding customers...")
        first_names = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Rohan", "Neha", "Arjun", "Aditi", "Karan", "Pooja", "Sanjay", "Ritu", "Vijay"]
        last_names = ["Sharma", "Verma", "Gupta", "Mehta", "Patel", "Reddy", "Joshi", "Iyer", "Nair", "Singh", "Rao", "Kumar", "Choudhury", "Das", "Sen"]
        merchants = ["MERCH_RETAIL_1", "MERCH_SAAS_2", "MERCH_EDU_3"]
        channels = ["EMAIL", "SMS", "WHATSAPP"]
        payment_methods = ["CARD", "UPI", "NETBANKING", "WALLET"]

        customers = []
        for i in range(1, 1001):
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            email = f"{name.lower().replace(' ', '.')}@example.com"
            phone = f"+91{random.randint(6000000000, 9999999999)}"
            clv = round(random.uniform(500, 150000), 2)
            preferred_channel = random.choice(channels)
            opt_out = random.random() < 0.02  # 2% opted out
            cust = Customer(
                id=f"CUST_{i:04d}",
                name=name,
                email=email,
                phone=phone,
                clv=clv,
                preferred_channel=preferred_channel,
                opt_out=opt_out,
                created_at=datetime.utcnow() - timedelta(days=random.randint(60, 365))
            )
            customers.append(cust)
            db.add(cust)
        db.commit()

        print("Seeding subscriptions...")
        subscriptions = []
        # Let's create about 1,500 subscriptions (some customers have multiple or one)
        for i in range(1, 1201):
            cust = random.choice(customers)
            status = random.choices(["ACTIVE", "PAST_DUE", "CANCELLED"], weights=[0.85, 0.10, 0.05], k=1)[0]
            mrr = round(random.uniform(299, 14999), 2)
            sub = Subscription(
                id=f"SUB_{i:05d}",
                customer_id=cust.id,
                status=status,
                mrr=mrr,
                next_billing_at=datetime.utcnow() + timedelta(days=random.randint(-15, 30)),
                failures_count=0 if status == "ACTIVE" else random.randint(1, 3),
                created_at=cust.created_at + timedelta(days=5)
            )
            subscriptions.append(sub)
            db.add(sub)
        db.commit()

        print("Seeding transactions...")
        transactions = []
        # Generate 10,000 transactions over the last 30 days
        start_date = datetime.utcnow() - timedelta(days=30)
        failure_reasons = [
            ("INSUFFICIENT_FUNDS", "Insufficient balance in customer account."),
            ("BANK_DECLINE", "Payment declined by issuing bank."),
            ("TEMPORARY_BANK_ISSUE", "Temporary issues at the issuing bank gateway."),
            ("TIMEOUT", "Transaction timed out during authentication."),
            ("AUTHENTICATION_FAILURE", "Customer failed 3D-Secure authentication."),
            ("EXPIRED_PAYMENT_METHOD", "Card expiration date has passed."),
            ("FRAUD_SUSPECTED", "Transaction blocked due to potential fraud/risk safety flag.")
        ]
        failure_weights = [0.40, 0.25, 0.15, 0.10, 0.05, 0.03, 0.02]

        for i in range(1, 10001):
            cust = random.choice(customers)
            merchant = random.choice(merchants)
            # Higher CLV customers do higher transaction amounts
            base_amount = 99 if cust.clv < 5000 else (4999 if cust.clv < 50000 else 45000)
            amount = round(base_amount + random.uniform(-base_amount * 0.3, base_amount * 0.5), 2)
            if amount <= 0:
                amount = 99.0

            # 22% failure rate overall for raw logs
            is_success = random.random() > 0.22
            status = "SUCCESS" if is_success else "FAILED"
            pay_method = random.choice(payment_methods)
            
            fail_code = None
            if not is_success:
                fail_code, _ = random.choices(failure_reasons, weights=failure_weights, k=1)[0]

            txn_time = start_date + timedelta(
                seconds=random.randint(0, int((datetime.utcnow() - start_date).total_seconds()))
            )

            txn = Transaction(
                id=f"TXN_{i:06d}",
                customer_id=cust.id,
                merchant_id=merchant,
                amount=amount,
                currency="INR",
                status=status,
                payment_method=pay_method,
                failure_reason=fail_code,
                created_at=txn_time
            )
            transactions.append(txn)
            db.add(txn)
        db.commit()

        # Group failed transactions to generate recovery cases
        failed_txns = [t for t in transactions if t.status == "FAILED"]
        print(f"Failed transactions generated: {len(failed_txns)}")

        print("Seeding checkout abandonment events...")
        abandoned_events = []
        for i in range(1, 501):
            cust = random.choice(customers)
            event_time = start_date + timedelta(
                seconds=random.randint(0, int((datetime.utcnow() - start_date).total_seconds()))
            )
            amount = round(random.uniform(499, 15000), 2)
            
            # Create a case for checkouts
            case_id = f"CASE_CH_{i:04d}"
            case = RecoveryCase(
                id=case_id,
                customer_id=cust.id,
                amount=amount,
                status="EXPIRED" if random.random() > 0.3 else "STOPPED",
                risk_score=random.randint(40, 75),
                revenue_at_risk=amount,
                failure_reason="CHECKOUT_ABANDONED",
                root_cause="checkout_abandonment",
                root_cause_explanation="Customer left checkout page without completing payment.",
                strategy_recommendation="SEND_PAYMENT_LINK",
                strategy_confidence=0.85,
                strategy_reason="Low-friction checkout recovery via payment link",
                attempts_count=1,
                created_at=event_time,
                updated_at=event_time + timedelta(hours=2)
            )
            db.add(case)
            
            event = PaymentEvent(
                id=f"EVT_CH_{i:04d}",
                case_id=case_id,
                event_type="CHECKOUT_ABANDONED",
                payload=f'{{"customer_id": "{cust.id}", "amount": {amount}}}',
                created_at=event_time
            )
            db.add(event)
        db.commit()

        print("Seeding subscription failure events...")
        # Link some of subscription failures to sub events
        for i in range(1, 1001):
            cust = random.choice(customers)
            sub = next((s for s in subscriptions if s.customer_id == cust.id), None)
            if not sub:
                continue
            event_time = start_date + timedelta(
                seconds=random.randint(0, int((datetime.utcnow() - start_date).total_seconds()))
            )
            
            case_id = f"CASE_SUB_{i:04d}"
            is_recovered = random.random() < 0.65
            status = "RECOVERED" if is_recovered else "STOPPED"
            
            case = RecoveryCase(
                id=case_id,
                customer_id=cust.id,
                subscription_id=sub.id,
                amount=sub.mrr,
                status=status,
                risk_score=random.randint(50, 90),
                revenue_at_risk=0.0 if is_recovered else sub.mrr,
                failure_reason="SUBSCRIPTION_PAYMENT_FAILED",
                root_cause="expired_payment_method" if random.random() < 0.5 else "insufficient_funds",
                root_cause_explanation="Auto-decline on recurring subscription charge.",
                strategy_recommendation="REQUEST_PAYMENT_METHOD_UPDATE" if random.random() < 0.5 else "RETRY_PAYMENT",
                strategy_confidence=0.88,
                strategy_reason="Mandated recurring recovery logic",
                attempts_count=random.randint(1, 2),
                created_at=event_time,
                updated_at=event_time + timedelta(hours=12),
                recovered_at=event_time + timedelta(hours=4) if is_recovered else None,
                recovery_time_minutes=240.0 if is_recovered else None,
                recovered_amount=sub.mrr if is_recovered else 0.0
            )
            db.add(case)

            event = PaymentEvent(
                id=f"EVT_SUB_{i:04d}",
                case_id=case_id,
                event_type="SUBSCRIPTION_PAYMENT_FAILED",
                payload=f'{{"customer_id": "{cust.id}", "subscription_id": "{sub.id}", "amount": {sub.mrr}}}',
                created_at=event_time
            )
            db.add(event)
        db.commit()

        print("Seeding transaction recovery cases...")
        # Create cases for transaction failures
        # Target: ~1,500 historic cases.
        # Status weights: RECOVERED: 65%, Active (AT_RISK/WAITING_APPROVAL/ACTION_EXECUTED): 18%, ESCALATED: 8%, STOPPED: 5%, EXPIRED: 4%
        case_statuses = ["RECOVERED", "AT_RISK", "WAITING_APPROVAL", "ACTION_EXECUTED", "ESCALATED", "STOPPED", "EXPIRED"]
        case_weights = [0.63, 0.10, 0.08, 0.07, 0.05, 0.04, 0.03]

        case_counter = 1
        for txn in failed_txns[:1500]:
            cust = txn.customer
            status = random.choices(case_statuses, weights=case_weights, k=1)[0]
            
            # Policy rules
            is_high_value = txn.amount > 20000.0
            if is_high_value and status in ["RECOVERED", "ACTION_EXECUTED"]:
                status = "WAITING_APPROVAL"  # High-value requires human approval
            
            is_fraud = txn.failure_reason == "FRAUD_SUSPECTED"
            if is_fraud:
                status = "ESCALATED"  # Fraud is always escalated

            # Map failure_reason to root_cause
            fail_map = {
                "INSUFFICIENT_FUNDS": ("insufficient_funds", "Customer has insufficient balance to complete transaction."),
                "BANK_DECLINE": ("bank_decline", "Bank declined the transaction without specific reason code."),
                "TEMPORARY_BANK_ISSUE": ("temporary_bank_issue", "Temporary bank switch timeout or core banking issue."),
                "TIMEOUT": ("timeout", "Network timeout between gateway and issuing bank."),
                "AUTHENTICATION_FAILURE": ("authentication_failure", "Customer failed 2-factor OTP authentication."),
                "EXPIRED_PAYMENT_METHOD": ("expired_payment_method", "Payment card expiry check failed."),
                "FRAUD_SUSPECTED": ("unknown", "High risk flag triggered by bank fraud check.")
            }
            rc, rc_expl = fail_map.get(txn.failure_reason, ("unknown", "Failed transaction."))

            # Strategy Selection
            strategy_recommendations = {
                "insufficient_funds": "SCHEDULE_RETRY",
                "bank_decline": "SEND_PAYMENT_LINK",
                "temporary_bank_issue": "RETRY_PAYMENT",
                "timeout": "RETRY_PAYMENT",
                "authentication_failure": "SEND_PAYMENT_LINK",
                "expired_payment_method": "REQUEST_PAYMENT_METHOD_UPDATE",
                "unknown": "ESCALATE_TO_HUMAN"
            }
            rec_strategy = strategy_recommendations.get(rc, "SEND_PAYMENT_LINK")

            risk_score = random.randint(30, 95)
            if is_high_value:
                risk_score += 15
            if is_fraud:
                risk_score = 99
            risk_score = min(risk_score, 100)

            # Revenue at risk
            revenue_at_risk = 0.0 if status in ["RECOVERED", "STOPPED", "EXPIRED"] else txn.amount

            case_id = f"CASE_TX_{case_counter:04d}"
            case_counter += 1

            recovery_time = None
            recovered_at = None
            if status == "RECOVERED":
                recovery_time = random.uniform(5.0, 180.0)  # minutes
                recovered_at = txn.created_at + timedelta(minutes=recovery_time)

            case = RecoveryCase(
                id=case_id,
                customer_id=cust.id,
                transaction_id=txn.id,
                amount=txn.amount,
                status=status,
                risk_score=risk_score,
                revenue_at_risk=revenue_at_risk,
                failure_reason=txn.failure_reason,
                root_cause=rc,
                root_cause_explanation=rc_expl,
                strategy_recommendation=rec_strategy,
                strategy_confidence=round(random.uniform(0.70, 0.98), 2),
                strategy_reason=f"Recommended {rec_strategy} due to {rc} diagnostic on failure.",
                attempts_count=random.randint(1, 2) if status in ["RECOVERED", "STOPPED", "EXPIRED"] else 1,
                created_at=txn.created_at,
                updated_at=txn.created_at + timedelta(minutes=recovery_time or 60),
                recovered_at=recovered_at,
                recovery_time_minutes=recovery_time,
                recovered_amount=txn.amount if status == "RECOVERED" else 0.0
            )
            db.add(case)

            # Add payment failure event
            evt = PaymentEvent(
                id=f"EVT_TX_{case_id}",
                case_id=case_id,
                transaction_id=txn.id,
                event_type="PAYMENT_FAILED",
                payload=f'{{"transaction_id": "{txn.id}", "failure_reason": "{txn.failure_reason}"}}',
                created_at=txn.created_at
            )
            db.add(evt)

            # Add Audit logs, Notification logs and actions for these historical cases
            # Let's write at least an analysis log
            risk_log = AuditLog(
                case_id=case_id,
                agent="RevenueRiskAgent",
                action="ANALYZE_RISK",
                decision=f"RISK_SCORE={risk_score}",
                reason=f"Analyzed risk profile for amount ₹{txn.amount}. Customer CLV is ₹{cust.clv}.",
                confidence=1.0,
                created_at=txn.created_at + timedelta(seconds=1)
            )
            db.add(risk_log)

            rc_log = AuditLog(
                case_id=case_id,
                agent="RootCauseAgent",
                action="DIAGNOSE",
                decision=rc,
                reason=rc_expl,
                confidence=0.95,
                created_at=txn.created_at + timedelta(seconds=2)
            )
            db.add(rc_log)

            # Execution logic check
            policy_check_str = "APPROVED"
            if is_high_value:
                policy_check_str = "BLOCKED_FOR_APPROVAL: High-value transaction (> ₹20,000)"
            elif is_fraud:
                policy_check_str = "BLOCKED_ESCALATED: Fraud threat score too high"
            elif cust.opt_out:
                policy_check_str = "BLOCKED_STOPPED: Customer opted out of notifications"

            strat_log = AuditLog(
                case_id=case_id,
                agent="StrategyAgent",
                action="RECOMMEND",
                decision=rec_strategy,
                reason=f"Selected {rec_strategy} for {cust.name} (Value: ₹{txn.amount})",
                confidence=0.90,
                policy_check=policy_check_str,
                created_at=txn.created_at + timedelta(seconds=3)
            )
            db.add(strat_log)

            # If recovering, write successful action
            if status == "RECOVERED":
                action = RecoveryAction(
                    id=f"ACT_{case_id}_1",
                    case_id=case_id,
                    action_type=rec_strategy,
                    status="SUCCESS",
                    payload=f'{{"recipient": "{cust.email if "EMAIL" in cust.preferred_channel else cust.phone}", "amount": {txn.amount}}}',
                    result='{"status": "success", "recovered_amount": ' + str(txn.amount) + '}',
                    approved_by="AI_SYSTEM" if not is_high_value else "HUMAN_USER",
                    idempotency_key=f"IDEMP_{case_id}_1",
                    created_at=txn.created_at + timedelta(seconds=10),
                    updated_at=recovered_at
                )
                db.add(action)

                # Add a communication log
                if rec_strategy in ["SEND_PAYMENT_LINK", "REQUEST_PAYMENT_METHOD_UPDATE"]:
                    msg_channel = cust.preferred_channel
                    msg_text = f"Hi {cust.name}, your payment of ₹{txn.amount} failed. Please complete it here: https://rzp.io/l/rec_{case_id}"
                    lang = "English" if random.random() > 0.5 else "Hinglish"
                    if lang == "Hinglish":
                        msg_text = f"Hi {cust.name}, aapka ₹{txn.amount} ka payment fail ho gaya hai. Please is link se complete karein: https://rzp.io/l/rec_{case_id}"

                    notif = NotificationLog(
                        id=f"NOT_{case_id}_1",
                        case_id=case_id,
                        channel=msg_channel,
                        recipient=cust.email if msg_channel == "EMAIL" else cust.phone,
                        content=msg_text,
                        language=lang,
                        status="SENT",
                        created_at=txn.created_at + timedelta(seconds=15)
                    )
                    db.add(notif)
            
            elif status == "ESCALATED":
                action = RecoveryAction(
                    id=f"ACT_{case_id}_1",
                    case_id=case_id,
                    action_type="ESCALATE_TO_HUMAN",
                    status="SUCCESS",
                    payload='{"escalated_reason": "' + rc_expl + '"}',
                    result='{"escalation_status": "assigned"}',
                    approved_by="AI_SYSTEM",
                    idempotency_key=f"IDEMP_{case_id}_1",
                    created_at=txn.created_at + timedelta(seconds=10)
                )
                db.add(action)

        db.commit()
        print("Data seeding completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
