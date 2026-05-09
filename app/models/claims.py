from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ClaimType(StrEnum):
    travel = "travel"
    home = "home"
    car = "car"


class ClaimStatus(StrEnum):
    submitted = "submitted"
    running = "running"
    awaiting_human_review = "awaiting_human_review"
    manual_handling = "manual_handling"
    report_ready = "report_ready"
    failed = "failed"


class UploadedDocument(BaseModel):
    document_type: str
    filename: str


class ClaimCreate(BaseModel):
    claim_id: str = Field(min_length=3)
    customer_id: str
    policy_id: str
    claim_type: ClaimType
    incident_date: date
    description: str = Field(min_length=20)
    claimed_amount: float = Field(gt=0)
    uploaded_documents: list[UploadedDocument] = Field(default_factory=list)


class ClaimRecord(ClaimCreate):
    status: ClaimStatus
    created_at: datetime
    updated_at: datetime


class ClassificationResult(BaseModel):
    claim_type: ClaimType
    complexity_level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)
    reasoning_summary: str


class PolicyClause(BaseModel):
    policy_type: ClaimType
    clause_id: str
    title: str
    text: str
    score: float = Field(ge=0, le=1)


class CoverageAnalysis(BaseModel):
    likely_covered: bool
    likely_excluded: bool
    uncertain: bool
    explanation: str


class MissingInfoResult(BaseModel):
    checklist: list[str]


class RiskSignal(BaseModel):
    code: str
    message: str
    severity: Literal["low", "medium", "high"]


class RiskAnalysis(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    risk_signals: list[RiskSignal]
    disclaimer: str = (
        "Risk signals are decision-support indicators only and are not a fraud accusation."
    )


class HumanReviewRequest(BaseModel):
    action: Literal["continue", "request_more_information", "manual_handling"]
    reviewer_id: str
    notes: str = ""


class TimelineEvent(BaseModel):
    node: str
    status: Literal["completed", "paused", "skipped", "failed"]
    summary: str
    timestamp: datetime


class ClaimReport(BaseModel):
    claim_overview: dict[str, Any]
    relevant_policy_clauses: list[PolicyClause]
    coverage_analysis: CoverageAnalysis
    missing_information: MissingInfoResult
    risk_signals: RiskAnalysis
    human_reviewer_notes: list[str]
    recommended_next_action: str
    disclaimer: str
    markdown_report: str


class ClaimDetail(BaseModel):
    claim: ClaimRecord
    classification: ClassificationResult | None = None
    policy_clauses: list[PolicyClause] = Field(default_factory=list)
    coverage_analysis: CoverageAnalysis | None = None
    missing_information: MissingInfoResult | None = None
    risk_analysis: RiskAnalysis | None = None
    timeline: list[TimelineEvent] = Field(default_factory=list)
    report: ClaimReport | None = None
    workflow_thread_id: str | None = None
