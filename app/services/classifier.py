from app.models.claims import ClaimCreate, ClaimType, ClassificationResult


class ClaimClassifier:
    def classify(self, claim: ClaimCreate) -> ClassificationResult:
        text = f"{claim.claim_type} {claim.description}".lower()
        scores = {
            ClaimType.travel: sum(k in text for k in ["flight", "hotel", "baggage", "travel", "trip"]),
            ClaimType.home: sum(k in text for k in ["leak", "water", "roof", "kitchen", "home", "burglary"]),
            ClaimType.car: sum(k in text for k in ["car", "vehicle", "collision", "parking", "windscreen"]),
        }
        detected = max(scores, key=scores.get) if max(scores.values()) > 0 else claim.claim_type
        high_markers = ["injury", "police", "liability", "theft", "fire", "multiple", "abroad"]
        complexity = "high" if claim.claimed_amount > 7500 or any(m in text for m in high_markers) else "medium"
        if claim.claimed_amount < 1000 and not any(m in text for m in high_markers):
            complexity = "low"
        confidence = 0.9 if detected == claim.claim_type else 0.62
        return ClassificationResult(
            claim_type=detected,
            complexity_level=complexity,
            confidence=confidence,
            reasoning_summary=(
                f"Classified from submitted type, amount EUR {claim.claimed_amount:,.0f}, "
                "and claim description keywords."
            ),
        )
