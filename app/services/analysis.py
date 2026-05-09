from datetime import date

from app.db.models import ClaimHistory, Policy
from app.models.claims import (
    ClaimCreate,
    CoverageAnalysis,
    MissingInfoResult,
    PolicyClause,
    RiskAnalysis,
    RiskSignal,
)


class CoverageAnalyzer:
    def analyze(self, claim: ClaimCreate, clauses: list[PolicyClause]) -> CoverageAnalysis:
        text = claim.description.lower()
        excluded_terms = ["wear and tear", "gradual", "unattended", "pre-existing", "alcohol"]
        likely_excluded = any(term in text for term in excluded_terms)
        likely_covered = not likely_excluded and any(c.score >= 0.45 for c in clauses)
        uncertain = claim.claimed_amount > 5000 or not likely_covered or likely_excluded
        return CoverageAnalysis(
            likely_covered=likely_covered,
            likely_excluded=likely_excluded,
            uncertain=uncertain,
            explanation=(
                "The assessment compares the claim narrative with retrieved policy clauses. "
                "It indicates likely coverage patterns only and leaves the decision to a reviewer."
            ),
        )


class MissingInformationDetector:
    REQUIRED = {
        "travel": {
            "invoice": ["invoice", "receipt"],
            "travel booking": ["booking", "itinerary"],
            "police report": ["police report"],
            "medical certificate": ["medical certificate"],
        },
        "home": {
            "photos": ["photo", "photos"],
            "repair quote": ["repair quote", "contractor quote"],
            "invoice": ["invoice", "receipt"],
        },
        "car": {
            "photos": ["photo", "photos"],
            "repair quote": ["repair quote", "garage estimate"],
            "police report": ["police report"],
        },
    }

    def detect(self, claim: ClaimCreate) -> MissingInfoResult:
        uploaded = " ".join(
            f"{doc.document_type} {doc.filename}".lower() for doc in claim.uploaded_documents
        )
        missing = []
        for label, aliases in self.REQUIRED[claim.claim_type.value].items():
            if not any(alias in uploaded for alias in aliases):
                missing.append(label)
        return MissingInfoResult(checklist=missing)


class RiskSignalDetector:
    def detect(
        self, claim: ClaimCreate, policy: Policy | None, history: list[ClaimHistory]
    ) -> RiskAnalysis:
        signals: list[RiskSignal] = []
        score = 0
        if claim.claimed_amount > 10000:
            score += 35
            signals.append(
                RiskSignal(
                    code="HIGH_AMOUNT",
                    message="Claimed amount is materially above the normal straight-through review band.",
                    severity="high",
                )
            )
        elif claim.claimed_amount > 5000:
            score += 20
            signals.append(
                RiskSignal(
                    code="ELEVATED_AMOUNT",
                    message="Claimed amount is elevated and should be reviewed carefully.",
                    severity="medium",
                )
            )
        if policy and not (policy.start_date <= claim.incident_date <= policy.end_date):
            score += 40
            signals.append(
                RiskSignal(
                    code="OUTSIDE_POLICY_PERIOD",
                    message="Incident date is outside the policy period.",
                    severity="high",
                )
            )
        recent_same_type = [
            h
            for h in history
            if h.claim_type == claim.claim_type.value and (date.today() - h.incident_date).days <= 365
        ]
        if len(recent_same_type) >= 2:
            score += 25
            signals.append(
                RiskSignal(
                    code="REPEATED_CLAIMS",
                    message="Customer has multiple recent claims of the same type.",
                    severity="medium",
                )
            )
        if "yesterday" in claim.description.lower() and claim.incident_date.year < date.today().year:
            score += 15
            signals.append(
                RiskSignal(
                    code="NARRATIVE_DATE_INCONSISTENCY",
                    message="Narrative timing appears inconsistent with the incident date.",
                    severity="medium",
                )
            )
        return RiskAnalysis(risk_score=min(score, 100), risk_signals=signals)
