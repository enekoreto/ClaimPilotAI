import json
from pathlib import Path

from app.models.claims import ClaimCreate
from app.services.analysis import CoverageAnalyzer, MissingInformationDetector
from app.services.classifier import ClaimClassifier
from app.services.policy_retriever import PolicyRetriever


def test_policy_retrieval_finds_expected_clause_for_all_cases():
    retriever = PolicyRetriever()
    for path in Path("data/test_cases").glob("*.json"):
        case = json.loads(path.read_text())
        claim = ClaimCreate.model_validate(case["claim"])
        clauses = retriever.retrieve(claim.claim_type, claim.description)
        assert case["expected"]["clause_id"] in [clause.clause_id for clause in clauses], path.name


def test_missing_documents_are_detected():
    case = json.loads(Path("data/test_cases/home_water_leak.json").read_text())
    claim = ClaimCreate.model_validate(case["claim"])
    result = MissingInformationDetector().detect(claim)
    assert {"repair quote", "invoice"}.issubset(result.checklist)


def test_classifier_uses_description_and_amount():
    claim = ClaimCreate.model_validate(json.loads(Path("data/test_cases/car_collision.json").read_text())["claim"])
    result = ClaimClassifier().classify(claim)
    assert result.claim_type == "car"
    assert result.confidence >= 0.75


def test_coverage_marks_exclusions_uncertain():
    case = json.loads(Path("data/test_cases/home_wear_and_tear.json").read_text())
    claim = ClaimCreate.model_validate(case["claim"])
    clauses = PolicyRetriever().retrieve(claim.claim_type, claim.description)
    result = CoverageAnalyzer().analyze(claim, clauses)
    assert result.likely_excluded is True
    assert result.uncertain is True
