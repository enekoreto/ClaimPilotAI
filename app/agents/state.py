from typing import Any, TypedDict


class ClaimWorkflowState(TypedDict, total=False):
    claim: dict[str, Any]
    classification: dict[str, Any]
    policy_clauses: list[dict[str, Any]]
    coverage_analysis: dict[str, Any]
    missing_information: dict[str, Any]
    risk_analysis: dict[str, Any]
    reviewer_notes: list[str]
    report: dict[str, Any]
    timeline: list[dict[str, Any]]
    requires_human_review: bool
    review_action: str
