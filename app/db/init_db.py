from datetime import date

from sqlalchemy.orm import Session

from app.db.models import ClaimHistory, Customer, Policy
from app.db.session import Base, engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_mock_data(db: Session) -> None:
    if db.query(Customer).first():
        return

    db.add_all(
        [
            Customer(customer_id="CUST-1001", name="Mila de Vries", segment="retail"),
            Customer(customer_id="CUST-1002", name="Jonas Bakker", segment="retail"),
            Customer(customer_id="CUST-1003", name="Sara Jansen", segment="retail"),
        ]
    )
    db.add_all(
        [
            Policy(
                policy_id="TRV-9001",
                customer_id="CUST-1001",
                policy_type="travel",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                excess_amount=75,
            ),
            Policy(
                policy_id="HOM-3001",
                customer_id="CUST-1002",
                policy_type="home",
                start_date=date(2025, 7, 1),
                end_date=date(2026, 6, 30),
                excess_amount=150,
            ),
            Policy(
                policy_id="CAR-7001",
                customer_id="CUST-1003",
                policy_type="car",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                excess_amount=250,
            ),
        ]
    )
    db.add_all(
        [
            ClaimHistory(
                customer_id="CUST-1003",
                claim_type="car",
                incident_date=date(2026, 2, 10),
                claimed_amount=1800,
                outcome="paid_after_review",
            ),
            ClaimHistory(
                customer_id="CUST-1003",
                claim_type="car",
                incident_date=date(2026, 3, 20),
                claimed_amount=2200,
                outcome="paid_after_review",
            ),
            ClaimHistory(
                customer_id="CUST-1001",
                claim_type="travel",
                incident_date=date(2025, 9, 4),
                claimed_amount=450,
                outcome="paid",
            ),
        ]
    )
    db.commit()
