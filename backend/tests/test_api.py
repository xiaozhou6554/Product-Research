import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import build_app


def client():
    return TestClient(build_app(str(Path(f".test-api-{uuid.uuid4().hex}.db"))))


def login(c, email="researcher@example.com", password="Research123!"):
    response = c.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def wait_for_success(c, headers, run_id):
    for _ in range(40):
        response = c.get(f"/api/v1/research-runs/{run_id}", headers=headers)
        assert response.status_code == 200
        body = response.json()
        if body["status"] == "SUCCEEDED":
            return body
        time.sleep(.02)
    raise AssertionError("run did not finish")


def test_create_idempotent_and_report_traceable():
    c = client()
    token = login(c)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "same-request"}
    payload = {"keyword": "travel organizer", "market": "US", "price_max": 32, "depth": "standard"}
    first = c.post("/api/v1/research-runs", json=payload, headers=headers)
    second = c.post("/api/v1/research-runs", json=payload, headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json()["run_id"] == second.json()["run_id"]
    run = wait_for_success(c, {"Authorization": f"Bearer {token}"}, first.json()["run_id"])
    assert run["analysis"]["profit"]["break_even_price"] > 0
    report = c.get(f"/api/v1/research-runs/{run['id']}/report", headers={"Authorization": f"Bearer {token}"})
    assert report.status_code == 200
    assert report.json()["report"]["traceability"]["evidence_count"] >= 3


def test_tenant_isolation_and_viewer_permission():
    c = client()
    token_a = login(c)
    created = c.post("/api/v1/research-runs", json={"keyword": "charger", "market": "US"}, headers={"Authorization": f"Bearer {token_a}"})
    run_id = created.json()["run_id"]
    token_b = login(c, "other@example.com", "Other123!")
    hidden = c.get(f"/api/v1/research-runs/{run_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert hidden.status_code == 404
    viewer = login(c, "viewer@example.com", "Viewer123!")
    forbidden = c.post("/api/v1/research-runs", json={"keyword": "charger", "market": "US"}, headers={"Authorization": f"Bearer {viewer}"})
    assert forbidden.status_code == 403


def test_validation_and_security_errors_do_not_leak_secrets():
    c = client()
    token = login(c)
    bad = c.post("/api/v1/research-runs", json={"keyword": "", "market": "CN"}, headers={"Authorization": f"Bearer {token}"})
    assert bad.status_code == 422
    assert "local-development-secret" not in bad.text
    assert c.get("/api/v1/research-runs/run_unknown", headers={"Authorization": f"Bearer {token}"}).status_code == 404


def test_report_chat_answers_with_traceable_context():
    c = client()
    token = login(c)
    created = c.post("/api/v1/research-runs", json={"keyword": "travel organizer", "market": "US"}, headers={"Authorization": f"Bearer {token}"})
    run = wait_for_success(c, {"Authorization": f"Bearer {token}"}, created.json()["run_id"])
    response = c.post(f"/api/v1/research-runs/{run['id']}/chat", json={"question": "毛利率和盈亏平衡售价是多少？"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "毛利率" in response.json()["answer"]
    assert "profit_calculation" in response.json()["citations"]
    assert response.json()["mode"] == "deterministic_fallback"
