from fastapi.testclient import TestClient

from app import app


def test_liveness_health():
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["version"] == "1.0.0"
    assert "X-Content-Type-Options" in r.headers
    assert r.headers["X-Frame-Options"] == "DENY"
