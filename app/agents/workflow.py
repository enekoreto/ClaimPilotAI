from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.types import Command, interrupt

from app.agents.state import ClaimWorkflowState
from app.models.claims import ClaimCreate, ClaimStatus, HumanReviewRequest, TimelineEvent
from app.services.analysis import CoverageAnalyzer, MissingInformationDetector, RiskSignalDetector
from app.services.claim_repository import ClaimRepository
from app.services.classifier import ClaimClassifier
from app.services.policy_retriever import PolicyRetriever
from app.services.reporting import ReportBuilder

CHECKPOINTER = MemorySaver()


def event(node: str, status: Literal["completed", "paused", "skipped", "failed"], summary: str) -> dict:
    return TimelineEvent(
        node=node,
        status=status,
        summary=summary,
        timestamp=datetime.now(timezone.utc),
    ).model_dump(mode="json")


class ClaimPilotWorkflow:
    def __init__(self, repo: ClaimRepository):
        self.repo = repo
        self.classifier = ClaimClassifier()
        self.retriever = PolicyRetriever()
        self.coverage = CoverageAnalyzer()
        self.missing = MissingInformationDetector()
        self.risk = RiskSignalDetector()
        self.reporting = ReportBuilder()
        self.graph = self._build_graph()

    def run(self, claim: ClaimCreate) -> dict[str, Any]:
        thread_id = f"claim-{claim.claim_id}"
        self.repo.set_status(claim.claim_id, ClaimStatus.running, thread_id=thread_id)
        result = self.graph.invoke(
            {"claim": claim.model_dump(mode="json"), "timeline": [], "reviewer_notes": []},
            config={"configurable": {"thread_id": thread_id}},
        )
        if "__interrupt__" in result:
            self.repo.set_status(claim.claim_id, ClaimStatus.awaiting_human_review, thread_id=thread_id)
            self._persist_state(claim.claim_id, result)
            return {"status": "awaiting_human_review", "thread_id": thread_id, "state": result}
        self.repo.set_status(claim.claim_id, ClaimStatus.report_ready, thread_id=thread_id)
        self._persist_state(claim.claim_id, result)
        return {"status": "report_ready", "thread_id": thread_id, "state": result}

    def resume(self, claim_id: str, review: HumanReviewRequest) -> dict[str, Any]:
        claim = self.repo.get_claim(claim_id)
        if not claim or not claim.workflow_thread_id:
            raise ValueError("Claim workflow is not waiting for review.")
        result = self.graph.invoke(
            Command(resume=review.model_dump()),
            config={"configurable": {"thread_id": claim.workflow_thread_id}},
        )
        if review.action == "manual_handling":
            self.repo.set_status(claim_id, ClaimStatus.manual_handling)
        else:
            self.repo.set_status(claim_id, ClaimStatus.report_ready)
        self._persist_state(claim_id, result)
        return {"status": self.repo.get_claim(claim_id).status, "state": result}

    def _build_graph(self):
        workflow = StateGraph(ClaimWorkflowState)
        workflow.add_node("classify_claim", self._classify)
        workflow.add_node("retrieve_policy", self._retrieve_policy)
        workflow.add_node("coverage_analysis", self._coverage_analysis)
        workflow.add_node("missing_information", self._missing_information)
        workflow.add_node("risk_signals", self._risk_signals)
        workflow.add_node("human_review", self._human_review)
        workflow.add_node("final_summary", self._final_summary)
        workflow.set_entry_point("classify_claim")
        workflow.add_edge("classify_claim", "retrieve_policy")
        workflow.add_edge("retrieve_policy", "coverage_analysis")
        workflow.add_edge("coverage_analysis", "missing_information")
        workflow.add_edge("missing_information", "risk_signals")
        workflow.add_conditional_edges(
            "risk_signals",
            self._route_after_risk,
            {"human_review": "human_review", "final_summary": "final_summary"},
        )
        workflow.add_conditional_edges(
            "human_review",
            self._route_after_review,
            {"final_summary": "final_summary", END: END},
        )
        workflow.add_edge("final_summary", END)
        return workflow.compile(checkpointer=CHECKPOINTER)

    def _claim(self, state: ClaimWorkflowState) -> ClaimCreate:
        return ClaimCreate.model_validate(state["claim"])

    def _classify(self, state: ClaimWorkflowState) -> ClaimWorkflowState:
        claim = self._claim(state)
        result = self.classifier.classify(claim)
        return {
            "classification": result.model_dump(mode="json"),
            "timeline": state.get("timeline", [])
            + [event("classify_claim", "completed", result.reasoning_summary)],
        }

    def _retrieve_policy(self, state: ClaimWorkflowState) -> ClaimWorkflowState:
        claim = self._claim(state)
        clauses = self.retriever.retrieve(claim.claim_type, claim.description)
        return {
            "policy_clauses": [c.model_dump(mode="json") for c in clauses],
            "timeline": state.get("timeline", [])
            + [event("retrieve_policy", "completed", f"Retrieved {len(clauses)} cited clauses.")],
        }

    def _coverage_analysis(self, state: ClaimWorkflowState) -> ClaimWorkflowState:
        claim = self._claim(state)
        from app.models.claims import PolicyClause

        parsed = [PolicyClause.model_validate(c) for c in state.get("policy_clauses", [])]
        result = self.coverage.analyze(claim, parsed)
        return {
            "coverage_analysis": result.model_dump(mode="json"),
            "timeline": state.get("timeline", [])
            + [event("coverage_analysis", "completed", "Coverage indicators generated.")],
        }

    def _missing_information(self, state: ClaimWorkflowState) -> ClaimWorkflowState:
        claim = self._claim(state)
        result = self.missing.detect(claim)
        return {
            "missing_information": result.model_dump(mode="json"),
            "timeline": state.get("timeline", [])
            + [
                event(
                    "missing_information",
                    "completed",
                    f"{len(result.checklist)} missing information item(s) detected.",
                )
            ],
        }

    def _risk_signals(self, state: ClaimWorkflowState) -> ClaimWorkflowState:
        claim = self._claim(state)
        result = self.risk.detect(
            claim, self.repo.policy(claim.policy_id), self.repo.claim_history(claim.customer_id)
        )
        classification = state["classification"]
        coverage = state["coverage_analysis"]
        requires_review = (
            classification["confidence"] < 0.75
            or result.risk_score >= 50
            or coverage["uncertain"]
        )
        return {
            "risk_analysis": result.model_dump(mode="json"),
            "requires_human_review": requires_review,
            "timeline": state.get("timeline", [])
            + [event("risk_signals", "completed", f"Risk score {result.risk_score}/100.")],
        }

    @staticmethod
    def _route_after_risk(state: ClaimWorkflowState) -> str:
        return "human_review" if state.get("requires_human_review") else "final_summary"

    def _human_review(self, state: ClaimWorkflowState) -> ClaimWorkflowState:
        payload = interrupt(
            {
                "reason": "Human review required due to uncertainty, confidence, or risk thresholds.",
                "coverage_uncertain": state["coverage_analysis"]["uncertain"],
                "risk_score": state["risk_analysis"]["risk_score"],
            }
        )
        review = HumanReviewRequest.model_validate(payload)
        notes = state.get("reviewer_notes", [])
        if review.notes:
            notes = notes + [f"{review.reviewer_id}: {review.notes}"]
        return {
            "review_action": review.action,
            "reviewer_notes": notes,
            "timeline": state.get("timeline", [])
            + [event("human_review", "completed", f"Reviewer action: {review.action}.")],
        }

    @staticmethod
    def _route_after_review(state: ClaimWorkflowState) -> str:
        return END if state.get("review_action") == "manual_handling" else "final_summary"

    def _final_summary(self, state: ClaimWorkflowState) -> ClaimWorkflowState:
        from app.models.claims import CoverageAnalysis, MissingInfoResult, PolicyClause, RiskAnalysis

        claim = self._claim(state)
        report = self.reporting.build(
            claim=claim,
            clauses=[PolicyClause.model_validate(c) for c in state.get("policy_clauses", [])],
            coverage=CoverageAnalysis.model_validate(state["coverage_analysis"]),
            missing=MissingInfoResult.model_validate(state["missing_information"]),
            risk=RiskAnalysis.model_validate(state["risk_analysis"]),
            reviewer_notes=state.get("reviewer_notes", []),
        )
        return {
            "report": report.model_dump(mode="json"),
            "timeline": state.get("timeline", [])
            + [event("final_summary", "completed", "Structured decision-support report generated.")],
        }

    def _persist_state(self, claim_id: str, state: dict[str, Any]) -> None:
        for key in [
            "classification",
            "policy_clauses",
            "coverage_analysis",
            "missing_information",
            "risk_analysis",
            "timeline",
            "report",
            "reviewer_notes",
            "requires_human_review",
        ]:
            if key in state:
                self.repo.save_artifact(claim_id, key, {"value": state[key]})
