from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.agents.workflow import ClaimPilotWorkflow
from app.db.init_db import init_db, seed_mock_data
from app.db.session import SessionLocal, get_db
from app.logging_config import configure_logging
from app.models.claims import (
    ClaimCreate,
    ClaimDetail,
    ClaimReport,
    ClaimStatus,
    HumanReviewRequest,
)
from app.services.claim_repository import ClaimRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(get_settings().log_level)
    init_db()
    with SessionLocal() as db:
        seed_mock_data(db)
    yield


app = FastAPI(
    title="ClaimPilot AI",
    description="Decision-support assistant for insurance claims. It never approves or rejects claims.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "claimpilot-ai"}


@app.get("/claims")
def list_claims(db: Session = Depends(get_db)):
    return ClaimRepository(db).list_claims()


@app.post("/claims", response_model=dict)
def create_claim(payload: ClaimCreate, db: Session = Depends(get_db)):
    repo = ClaimRepository(db)
    try:
        claim = repo.create_claim(payload)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Claim ID already exists.") from exc
    return {"claim": claim, "disclaimer": "Decision-support only; no automated claim decision."}


@app.get("/claims/{claim_id}", response_model=ClaimDetail)
def get_claim(claim_id: str, db: Session = Depends(get_db)):
    repo = ClaimRepository(db)
    claim = repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    artifacts = repo.artifacts(claim_id)
    return ClaimDetail(
        claim=repo.to_record(claim),
        classification=(artifacts.get("classification") or {}).get("value"),
        policy_clauses=(artifacts.get("policy_clauses") or {}).get("value", []),
        coverage_analysis=(artifacts.get("coverage_analysis") or {}).get("value"),
        missing_information=(artifacts.get("missing_information") or {}).get("value"),
        risk_analysis=(artifacts.get("risk_analysis") or {}).get("value"),
        timeline=(artifacts.get("timeline") or {}).get("value", []),
        report=(artifacts.get("report") or {}).get("value"),
        workflow_thread_id=claim.workflow_thread_id,
    )


@app.post("/claims/{claim_id}/run")
def run_claim(claim_id: str, db: Session = Depends(get_db)):
    repo = ClaimRepository(db)
    claim_row = repo.get_claim(claim_id)
    if not claim_row:
        raise HTTPException(status_code=404, detail="Claim not found.")
    payload = ClaimCreate(
        claim_id=claim_row.claim_id,
        customer_id=claim_row.customer_id,
        policy_id=claim_row.policy_id,
        claim_type=claim_row.claim_type,
        incident_date=claim_row.incident_date,
        description=claim_row.description,
        claimed_amount=claim_row.claimed_amount,
        uploaded_documents=claim_row.uploaded_documents or [],
    )
    return ClaimPilotWorkflow(repo).run(payload)


@app.post("/claims/{claim_id}/review")
def review_claim(claim_id: str, payload: HumanReviewRequest, db: Session = Depends(get_db)):
    repo = ClaimRepository(db)
    claim = repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    if claim.status != ClaimStatus.awaiting_human_review.value:
        raise HTTPException(status_code=409, detail="Claim is not awaiting human review.")
    try:
        return ClaimPilotWorkflow(repo).resume(claim_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/claims/{claim_id}/report", response_model=ClaimReport)
def get_report(claim_id: str, db: Session = Depends(get_db)):
    repo = ClaimRepository(db)
    claim = repo.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
    report = (repo.artifacts(claim_id).get("report") or {}).get("value")
    if not report:
        raise HTTPException(status_code=404, detail="Report not ready.")
    return report
