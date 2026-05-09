from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.session import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    segment: Mapped[str] = mapped_column(String(80))


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"))
    policy_type: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    excess_amount: Mapped[float] = mapped_column(Float, default=0)


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    policy_id: Mapped[str] = mapped_column(String(64), index=True)
    claim_type: Mapped[str] = mapped_column(String(32))
    incident_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(Text)
    claimed_amount: Mapped[float] = mapped_column(Float)
    uploaded_documents: Mapped[list[dict]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(64), default="submitted")
    workflow_thread_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    artifacts: Mapped[list["ClaimArtifact"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimHistory(Base):
    __tablename__ = "claim_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    claim_type: Mapped[str] = mapped_column(String(32))
    incident_date: Mapped[date] = mapped_column(Date)
    claimed_amount: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(80))


class ClaimArtifact(Base):
    __tablename__ = "claim_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    claim: Mapped[Claim] = relationship(back_populates="artifacts")
