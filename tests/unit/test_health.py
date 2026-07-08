"""Smoke test for the Day 1 app skeleton."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_model"]  # driven by env, defaults to qwen3:4b-instruct
