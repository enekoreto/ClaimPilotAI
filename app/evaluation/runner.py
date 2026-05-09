import json
from pathlib import Path
from datetime import date
from types import SimpleNamespace

from pydantic import ValidationError

from app.models.claims import ClaimCreate, ClaimReport
from app.services.analysis import CoverageAnalyzer, MissingInformationDetector, RiskSignalDetector
from app.services.classifier import ClaimClassifier
from app.services.policy_retriever import PolicyRetriever
from app.services.reporting import ReportBuilder


def run_evaluation(test_case_dir: str = "data/test_cases") -> dict:
    retriever = PolicyRetriever()
    classifier = ClaimClassifier()
    coverage = CoverageAnalyzer()
    missing = MissingInformationDetector()
    risk = RiskSignalDetector()
    reporting = ReportBuilder()
    results = []
    for path in sorted(Path(test_case_dir).glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        claim = ClaimCreate.model_validate(case["claim"])
        classification = classifier.classify(claim)
        clauses = retriever.retrieve(claim.claim_type, claim.description)
        coverage_result = coverage.analyze(claim, clauses)
        missing_result = missing.detect(claim)
        policy = _mock_policy(claim.policy_id)
        risk_result = risk.detect(claim, policy, [])
        report = reporting.build(claim, clauses, coverage_result, missing_result, risk_result, [])
        try:
            ClaimReport.model_validate(report.model_dump())
            schema_ok = True
        except ValidationError:
            schema_ok = False
        expected = case["expected"]
        results.append(
            {
                "case": path.stem,
                "classification_ok": classification.claim_type.value == expected["claim_type"],
                "clauses_ok": expected["clause_id"] in [c.clause_id for c in clauses],
                "missing_ok": set(expected["missing_documents"]).issubset(missing_result.checklist),
                "human_review_ok": (risk_result.risk_score >= 50 or coverage_result.uncertain)
                == expected["human_review"],
                "schema_ok": schema_ok,
            }
        )
    return {"passed": all(all(v for k, v in row.items() if k != "case") for row in results), "results": results}


def _mock_policy(policy_id: str):
    windows = {
        "TRV-9001": (date(2026, 1, 1), date(2026, 12, 31)),
        "HOM-3001": (date(2025, 7, 1), date(2026, 6, 30)),
        "CAR-7001": (date(2026, 1, 1), date(2026, 12, 31)),
    }
    start, end = windows.get(policy_id, (date(2026, 1, 1), date(2026, 12, 31)))
    return SimpleNamespace(start_date=start, end_date=end)


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=2))
