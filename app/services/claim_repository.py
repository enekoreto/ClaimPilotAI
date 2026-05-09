from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Claim, ClaimArtifact, ClaimHistory, Policy
from app.models.claims import ClaimCreate, ClaimRecord, ClaimStatus


class ClaimRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_claim(self, payload: ClaimCreate) -> ClaimRecord:
        claim = Claim(
            claim_id=payload.claim_id,
            customer_id=payload.customer_id,
            policy_id=payload.policy_id,
            claim_type=payload.claim_type.value,
            incident_date=payload.incident_date,
            description=payload.description,
            claimed_amount=payload.claimed_amount,
            uploaded_documents=[doc.model_dump() for doc in payload.uploaded_documents],
            status=ClaimStatus.submitted.value,
        )
        self.db.add(claim)
        self.db.commit()
        self.db.refresh(claim)
        return self.to_record(claim)

    def get_claim(self, claim_id: str) -> Claim | None:
        return self.db.get(Claim, claim_id)

    def list_claims(self) -> list[ClaimRecord]:
        return [self.to_record(c) for c in self.db.query(Claim).order_by(Claim.created_at.desc()).all()]

    def set_status(self, claim_id: str, status: ClaimStatus, thread_id: str | None = None) -> None:
        claim = self.db.get(Claim, claim_id)
        if claim:
            claim.status = status.value
            if thread_id:
                claim.workflow_thread_id = thread_id
            self.db.commit()

    def save_artifact(self, claim_id: str, artifact_type: str, payload: dict[str, Any]) -> None:
        existing = (
            self.db.query(ClaimArtifact)
            .filter(ClaimArtifact.claim_id == claim_id, ClaimArtifact.artifact_type == artifact_type)
            .first()
        )
        if existing:
            existing.payload = payload
        else:
            self.db.add(
                ClaimArtifact(claim_id=claim_id, artifact_type=artifact_type, payload=payload)
            )
        self.db.commit()

    def artifacts(self, claim_id: str) -> dict[str, Any]:
        rows = self.db.query(ClaimArtifact).filter(ClaimArtifact.claim_id == claim_id).all()
        return {row.artifact_type: row.payload for row in rows}

    def policy(self, policy_id: str) -> Policy | None:
        return self.db.get(Policy, policy_id)

    def claim_history(self, customer_id: str) -> list[ClaimHistory]:
        return (
            self.db.query(ClaimHistory)
            .filter(ClaimHistory.customer_id == customer_id)
            .order_by(ClaimHistory.incident_date.desc())
            .all()
        )

    @staticmethod
    def to_record(claim: Claim) -> ClaimRecord:
        return ClaimRecord(
            claim_id=claim.claim_id,
            customer_id=claim.customer_id,
            policy_id=claim.policy_id,
            claim_type=claim.claim_type,
            incident_date=claim.incident_date,
            description=claim.description,
            claimed_amount=claim.claimed_amount,
            uploaded_documents=claim.uploaded_documents or [],
            status=claim.status,
            created_at=claim.created_at or datetime.now(timezone.utc),
            updated_at=claim.updated_at or datetime.now(timezone.utc),
        )
