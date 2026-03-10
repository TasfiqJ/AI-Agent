"""Tests for the web dashboard endpoints and state management."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from guardian.dashboard.models import (
    RunHistoryEntry,
    ScanHistoryEntry,
    ScanResponse,
)
from guardian.dashboard.state import DashboardState, dashboard_state
from guardian.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_dashboard_state() -> None:
    """Clear dashboard state between tests."""
    dashboard_state.run_history.clear()
    dashboard_state.scan_history.clear()
    dashboard_state.event_queues.clear()
    dashboard_state.active_tasks.clear()


# ── Dashboard HTML ─────────────────────────────────────────


def test_dashboard_page_serves_html(client: TestClient) -> None:
    """GET /dashboard/ should serve the HTML dashboard."""
    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "test-guardian" in response.text


# ── Ping ───────────────────────────────────────────────────


def test_ping_returns_pong(client: TestClient) -> None:
    response = client.get("/dashboard/api/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["pong"] is True
    assert "timestamp" in data


# ── Scan ───────────────────────────────────────────────────


def test_scan_flask_project(client: TestClient) -> None:
    """Scan the demo Flask project and verify endpoints detected."""
    demo_path = str(Path(__file__).parent.parent.parent / "demo" / "flask-todo-api")
    response = client.post(
        "/dashboard/api/scan",
        json={"repo_path": demo_path},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["framework"] == "flask"
    assert data["endpoints_detected"] == 6
    assert len(data["endpoints"]) == 6
    assert "message" in data


def test_scan_fastapi_project(client: TestClient) -> None:
    demo_path = str(Path(__file__).parent.parent.parent / "demo" / "fastapi-notes")
    response = client.post(
        "/dashboard/api/scan",
        json={"repo_path": demo_path},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["framework"] == "fastapi"
    assert data["endpoints_detected"] == 6


def test_scan_unknown_project(client: TestClient, tmp_path: Path) -> None:
    response = client.post(
        "/dashboard/api/scan",
        json={"repo_path": str(tmp_path)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["framework"] == "unknown"
    assert data["endpoints_detected"] == 0


def test_scan_records_to_history(client: TestClient) -> None:
    """Scanning should record an entry in scan history."""
    demo_path = str(Path(__file__).parent.parent.parent / "demo" / "flask-todo-api")
    client.post("/dashboard/api/scan", json={"repo_path": demo_path})

    assert len(dashboard_state.scan_history) == 1
    entry = dashboard_state.scan_history[0]
    assert entry.framework == "flask"
    assert entry.endpoints_detected == 6


def test_scan_requires_repo_path(client: TestClient) -> None:
    response = client.post("/dashboard/api/scan", json={})
    assert response.status_code == 422


# ── Eval Repos ─────────────────────────────────────────────


def test_list_eval_repos(client: TestClient) -> None:
    response = client.get("/dashboard/api/eval/repos")
    assert response.status_code == 200
    repos = response.json()
    assert isinstance(repos, list)
    assert len(repos) >= 3  # At least the 3 demo repos

    # Each repo has the expected fields
    for repo in repos:
        assert "name" in repo
        assert "path" in repo
        assert "framework" in repo
        assert "expected_endpoints" in repo
        assert "available" in repo


# ── History ────────────────────────────────────────────────


def test_history_empty(client: TestClient) -> None:
    response = client.get("/dashboard/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["runs"] == []
    assert data["scans"] == []


def test_history_after_scan(client: TestClient) -> None:
    demo_path = str(Path(__file__).parent.parent.parent / "demo" / "flask-todo-api")
    client.post("/dashboard/api/scan", json={"repo_path": demo_path})

    response = client.get("/dashboard/api/history")
    assert response.status_code == 200
    data = response.json()
    assert len(data["scans"]) == 1
    assert data["scans"][0]["framework"] == "flask"


# ── Run Start ──────────────────────────────────────────────


def test_start_run_returns_run_id(client: TestClient, tmp_path: Path) -> None:
    response = client.post(
        "/dashboard/api/run/start",
        json={
            "repo_path": str(tmp_path),
            "permission_mode": "trust",
            "max_iterations": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["run_id"].startswith("run-")
    assert data["message"] == "Run started"


# ── SSE Events ─────────────────────────────────────────────


def test_run_events_not_found(client: TestClient) -> None:
    """Requesting events for a non-existent run should return an error event."""
    response = client.get("/dashboard/api/run/events/nonexistent")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "not found" in response.text


# ── Browse ────────────────────────────────────────────────


def test_browse_root(client: TestClient) -> None:
    """Browse with no path should return drives (Windows) or root dirs."""
    response = client.get("/dashboard/api/browse")
    assert response.status_code == 200
    data = response.json()
    assert "current" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0


def test_browse_specific_path(client: TestClient, tmp_path: Path) -> None:
    """Browse a specific directory should list its subdirectories."""
    # Create some subdirs
    (tmp_path / "subdir_a").mkdir()
    (tmp_path / "subdir_b").mkdir()
    (tmp_path / "file.txt").write_text("hello")  # files should be excluded

    response = client.get(f"/dashboard/api/browse?path={tmp_path}")
    assert response.status_code == 200
    data = response.json()
    assert data["current"] == str(tmp_path)
    assert len(data["items"]) == 2
    names = [item["name"] for item in data["items"]]
    assert "subdir_a" in names
    assert "subdir_b" in names


def test_browse_nonexistent_path(client: TestClient) -> None:
    """Browse a non-existent path should return error."""
    response = client.get("/dashboard/api/browse?path=Z:\\nonexistent\\path")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


def test_browse_hidden_dirs_excluded(client: TestClient, tmp_path: Path) -> None:
    """Hidden directories (starting with .) should be excluded."""
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "visible").mkdir()

    response = client.get(f"/dashboard/api/browse?path={tmp_path}")
    data = response.json()
    names = [item["name"] for item in data["items"]]
    assert "visible" in names
    assert ".hidden" not in names


# ── DashboardState Unit Tests ──────────────────────────────


class TestDashboardState:
    def test_record_scan(self) -> None:
        state = DashboardState()
        state.record_scan(
            repo_path="/tmp/test",
            framework="flask",
            endpoints_detected=5,
            endpoints=[{"method": "GET", "path": "/test"}],
        )
        assert len(state.scan_history) == 1
        assert state.scan_history[0].framework == "flask"
        assert state.scan_history[0].endpoints_detected == 5

    def test_record_scan_limit(self) -> None:
        """History should be capped at 50 entries."""
        state = DashboardState()
        for i in range(60):
            state.record_scan(
                repo_path=f"/tmp/test-{i}",
                framework="flask",
                endpoints_detected=i,
                endpoints=[],
            )
        assert len(state.scan_history) == 50
        # Most recent should be first
        assert state.scan_history[0].endpoints_detected == 59

    def test_record_run(self) -> None:
        state = DashboardState()
        state.record_run(
            run_id="run-abc123",
            repo_path="/tmp/test",
            started_at="2026-01-01T00:00:00Z",
            summary={
                "state": "COMPLETE",
                "termination_reason": "SUCCESS",
                "iterations": 2,
                "files_changed": ["test_api.py"],
            },
        )
        assert len(state.run_history) == 1
        assert state.run_history[0].run_id == "run-abc123"
        assert state.run_history[0].state == "COMPLETE"

    def test_record_run_limit(self) -> None:
        state = DashboardState()
        for i in range(60):
            state.record_run(
                run_id=f"run-{i}",
                repo_path="/tmp/test",
                started_at="2026-01-01T00:00:00Z",
                summary={"state": "COMPLETE"},
            )
        assert len(state.run_history) == 50

    def test_create_and_remove_event_queue(self) -> None:
        state = DashboardState()
        queue = state.create_event_queue("run-test")
        assert "run-test" in state.event_queues
        assert queue is state.event_queues["run-test"]

        state.remove_event_queue("run-test")
        assert "run-test" not in state.event_queues

    def test_remove_nonexistent_queue(self) -> None:
        """Removing a non-existent queue should not raise."""
        state = DashboardState()
        state.remove_event_queue("does-not-exist")  # No error


# ── Pydantic Model Tests ──────────────────────────────────


class TestDashboardModels:
    def test_scan_response_model(self) -> None:
        resp = ScanResponse(
            framework="flask",
            endpoints_detected=3,
            endpoints=[{"method": "GET", "path": "/api"}],
            message="Found 3 endpoints",
        )
        assert resp.framework == "flask"
        assert resp.endpoints_detected == 3

    def test_run_history_entry_defaults(self) -> None:
        entry = RunHistoryEntry(
            run_id="run-test",
            repo_path="/tmp",
            started_at="2026-01-01T00:00:00Z",
            state="IDLE",
        )
        assert entry.completed_at is None
        assert entry.framework is None
        assert entry.endpoints_detected == 0
        assert entry.iterations == 0
        assert entry.files_changed == []
        assert entry.termination_reason is None

    def test_scan_history_entry(self) -> None:
        entry = ScanHistoryEntry(
            timestamp="2026-01-01T00:00:00Z",
            repo_path="/tmp/test",
            framework="fastapi",
            endpoints_detected=4,
            endpoints=[],
        )
        assert entry.framework == "fastapi"
        data = entry.model_dump()
        assert "timestamp" in data
        assert "repo_path" in data
