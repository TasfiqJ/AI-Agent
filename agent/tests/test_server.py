"""Tests for the FastAPI server."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from guardian.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


def test_init_endpoint(client: TestClient) -> None:
    # Point at the demo flask-todo-api
    demo_path = str(Path(__file__).parent.parent.parent / "demo" / "flask-todo-api")
    response = client.post("/init", json={"repo_path": demo_path})
    assert response.status_code == 200
    data = response.json()
    assert data["framework"] == "flask"
    assert data["endpoints_detected"] == 6
    assert len(data["endpoints"]) == 6


def test_init_unknown_repo(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/init", json={"repo_path": str(tmp_path)})
    assert response.status_code == 200
    data = response.json()
    assert data["framework"] == "unknown"
    assert data["endpoints_detected"] == 0


def test_init_requires_repo_path(client: TestClient) -> None:
    response = client.post("/init", json={})
    assert response.status_code == 422  # Validation error


def test_status_endpoint_no_run(client: TestClient) -> None:
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "IDLE"
    assert data["run_id"] is None


def test_revert_endpoint_no_run(client: TestClient) -> None:
    response = client.post("/revert", json={})
    assert response.status_code == 200
    data = response.json()
    assert "No active run" in data["message"]


def test_run_endpoint_returns_sse(client: TestClient, tmp_path: Path) -> None:
    """Test that /run returns a streaming response."""
    response = client.post(
        "/run",
        json={
            "repo_path": str(tmp_path),
            "permission_mode": "trust",
            "max_iterations": 1,
        },
    )
    # The endpoint returns SSE (even if it errors because no Ollama),
    # so it should be a 200 with event-stream content type
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
