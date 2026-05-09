def _claim_payload():
    return {
        "claim_id": "API-TRV-001",
        "customer_id": "CUST-1001",
        "policy_id": "TRV-9001",
        "claim_type": "travel",
        "incident_date": "2026-03-15",
        "description": "Checked baggage was delayed by the airline for 30 hours after my flight to Lisbon.",
        "claimed_amount": 420,
        "uploaded_documents": [{"document_type": "invoice", "filename": "items_invoice.pdf"}],
    }


def test_create_get_run_and_report(client):
    created = client.post("/claims", json=_claim_payload())
    assert created.status_code == 200
    claim = client.get("/claims/API-TRV-001")
    assert claim.status_code == 200

    run = client.post("/claims/API-TRV-001/run")
    assert run.status_code == 200
    assert run.json()["status"] in {"report_ready", "awaiting_human_review"}

    detail = client.get("/claims/API-TRV-001").json()
    if detail["claim"]["status"] == "awaiting_human_review":
        review = client.post(
            "/claims/API-TRV-001/review",
            json={"action": "continue", "reviewer_id": "reviewer-1", "notes": "Proceed after checking documents."},
        )
        assert review.status_code == 200

    report = client.get("/claims/API-TRV-001/report")
    assert report.status_code == 200
    assert report.json()["claim_overview"]["claim_id"] == "API-TRV-001"
    assert "does not approve" in report.json()["disclaimer"]


def test_human_review_resume_generates_report(client):
    payload = _claim_payload()
    payload["claim_id"] = "API-CAR-REVIEW"
    payload["customer_id"] = "CUST-1003"
    payload["policy_id"] = "CAR-7001"
    payload["claim_type"] = "car"
    payload["description"] = "Collision damage to the insured vehicle with a high repair estimate for bumper and headlight."
    payload["claimed_amount"] = 6400
    payload["uploaded_documents"] = [{"document_type": "photos", "filename": "damage_photos.zip"}]

    assert client.post("/claims", json=payload).status_code == 200
    run = client.post("/claims/API-CAR-REVIEW/run")
    assert run.status_code == 200
    assert run.json()["status"] == "awaiting_human_review"

    review = client.post(
        "/claims/API-CAR-REVIEW/review",
        json={"action": "continue", "reviewer_id": "reviewer-1", "notes": "Continue with manual evidence check."},
    )
    assert review.status_code == 200

    detail = client.get("/claims/API-CAR-REVIEW").json()
    assert detail["claim"]["status"] == "report_ready"
    assert detail["report"]["human_reviewer_notes"] == [
        "reviewer-1: Continue with manual evidence check."
    ]


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
