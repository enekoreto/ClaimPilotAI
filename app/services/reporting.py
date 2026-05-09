from app.models.claims import (
    ClaimCreate,
    ClaimReport,
    CoverageAnalysis,
    MissingInfoResult,
    PolicyClause,
    RiskAnalysis,
)


class ReportBuilder:
    def build(
        self,
        claim: ClaimCreate,
        clauses: list[PolicyClause],
        coverage: CoverageAnalysis,
        missing: MissingInfoResult,
        risk: RiskAnalysis,
        reviewer_notes: list[str],
    ) -> ClaimReport:
        if risk.risk_score >= 70 or coverage.uncertain:
            action = "Manual review recommended before any customer-facing decision."
        elif missing.checklist:
            action = "Request missing information before completing claim assessment."
        else:
            action = "Reviewer can continue standard assessment using the cited evidence."

        overview = claim.model_dump()
        overview["incident_date"] = str(claim.incident_date)
        overview["uploaded_documents"] = [d.model_dump() for d in claim.uploaded_documents]

        markdown = self._markdown(claim, clauses, coverage, missing, risk, reviewer_notes, action)
        return ClaimReport(
            claim_overview=overview,
            relevant_policy_clauses=clauses,
            coverage_analysis=coverage,
            missing_information=missing,
            risk_signals=risk,
            human_reviewer_notes=reviewer_notes,
            recommended_next_action=action,
            disclaimer=(
                "ClaimPilot AI is a decision-support tool. It does not approve, reject, or settle claims."
            ),
            markdown_report=markdown,
        )

    @staticmethod
    def _markdown(
        claim: ClaimCreate,
        clauses: list[PolicyClause],
        coverage: CoverageAnalysis,
        missing: MissingInfoResult,
        risk: RiskAnalysis,
        notes: list[str],
        action: str,
    ) -> str:
        clause_lines = "\n".join(f"- {c.clause_id}: {c.title}" for c in clauses)
        missing_lines = "\n".join(f"- {item}" for item in missing.checklist) or "- None identified"
        risk_lines = "\n".join(f"- {s.code}: {s.message}" for s in risk.risk_signals) or "- None identified"
        note_lines = "\n".join(f"- {note}" for note in notes) or "- No reviewer notes"
        return f"""# ClaimPilot AI Review Report

## Claim overview
- Claim ID: {claim.claim_id}
- Customer ID: {claim.customer_id}
- Policy ID: {claim.policy_id}
- Claim type: {claim.claim_type}
- Claimed amount: EUR {claim.claimed_amount:,.2f}

## Relevant policy clauses
{clause_lines}

## Coverage analysis
Likely covered: {coverage.likely_covered}
Likely excluded: {coverage.likely_excluded}
Uncertain: {coverage.uncertain}

{coverage.explanation}

## Missing information
{missing_lines}

## Risk signals
Risk score: {risk.risk_score}/100
{risk_lines}

## Human reviewer notes
{note_lines}

## Recommended next action
{action}

Decision-support only: this report does not approve, reject, or settle the claim.
"""
