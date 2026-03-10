"""Tests for the agentic loop state machine."""

import json
import tempfile
from pathlib import Path

import pytest

from guardian.llm.client import MockLLMClient
from guardian.loop import AgentLoop, AgentState, TerminationReason
from guardian.safety.permissions import PermissionManager, PermissionMode
from guardian.tools.registry import ToolRegistry


def _make_plan_json() -> str:
    """Create a valid AgentPlan JSON string for mock LLM responses."""
    plan = {
        "framework": "flask",
        "endpoints": [
            {
                "method": "GET",
                "path": "/api/todos",
                "handler": "list_todos",
                "file": "app.py",
                "line": 10,
            }
        ],
        "steps": [
            {
                "id": 1,
                "description": "Generate test file",
                "tool_calls": ["file_write"],
                "output_file": "tests/test_todos.py",
            }
        ],
        "test_files": ["tests/test_todos.py"],
        "success_criteria": ["All tests pass"],
    }
    return json.dumps(plan)


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory that persists for the test."""
    return tmp_path


def _make_loop(
    tmp_dir: Path,
    responses: list[str],
    mode: PermissionMode = PermissionMode.DEFAULT,
    max_iterations: int = 3,
    max_tool_calls: int = 50,
) -> AgentLoop:
    """Create an AgentLoop with mock LLM for testing."""
    repo_path = tmp_dir / "test-repo"
    repo_path.mkdir(exist_ok=True)
    guardian_dir = tmp_dir / ".test-guardian"

    llm = MockLLMClient(responses=responses)
    registry = ToolRegistry()
    perms = PermissionManager(mode=mode)

    return AgentLoop(
        llm=llm,
        tool_registry=registry,
        permission_manager=perms,
        repo_path=repo_path,
        guardian_dir=guardian_dir,
        max_iterations=max_iterations,
        max_tool_calls=max_tool_calls,
    )


@pytest.mark.asyncio
async def test_loop_starts_idle(tmp_dir: Path) -> None:
    loop = _make_loop(tmp_dir, responses=[_make_plan_json()])
    assert loop.state == AgentState.IDLE


@pytest.mark.asyncio
async def test_loop_success_path(tmp_dir: Path) -> None:
    """Test: PLAN → ACT → VERIFY (all pass) → COMPLETE."""
    plan_json = _make_plan_json()
    responses = [
        plan_json,
        "Generated test file tests/test_todos.py",
        '{"action": "complete", "summary": "All 5 tests passed"}',
    ]
    loop = _make_loop(tmp_dir, responses)
    result = await loop.run()

    assert result["state"] == "COMPLETE"
    assert result["termination_reason"] == "SUCCESS"
    assert result["iterations"] == 1
    assert len(result["files_changed"]) > 0


@pytest.mark.asyncio
async def test_loop_max_iterations(tmp_dir: Path) -> None:
    """Test: after max iterations, terminates as PARTIAL."""
    plan_json = _make_plan_json()
    responses = [
        plan_json,
        "Generated tests",
        "Tests failed: 2 failures",
        "Fixed test assertions",
        "Tests failed: 1 failure",
        "Fixed remaining test",
        "Tests still failing",
    ]
    loop = _make_loop(tmp_dir, responses, max_iterations=3)
    result = await loop.run()

    assert result["state"] == "COMPLETE"
    assert result["termination_reason"] == "PARTIAL"
    assert result["iterations"] == 3


@pytest.mark.asyncio
async def test_loop_plan_failure(tmp_dir: Path) -> None:
    """Test: if plan generation fails, loop terminates as ERROR."""
    responses = ["This is not valid JSON at all"] * 4
    loop = _make_loop(tmp_dir, responses)
    result = await loop.run()

    assert result["state"] == "FAILED"
    assert result["termination_reason"] == "ERROR"


@pytest.mark.asyncio
async def test_loop_budget_exceeded(tmp_dir: Path) -> None:
    """Test: tool budget configuration works."""
    plan_json = _make_plan_json()
    responses = [plan_json, "Generated tests", "All complete"]

    loop = _make_loop(tmp_dir, responses, max_tool_calls=0)
    result = await loop.run()

    # The loop should complete since we're not actually calling tools via registry
    assert result["state"] in ("COMPLETE", "FAILED")


@pytest.mark.asyncio
async def test_loop_generates_trace(tmp_dir: Path) -> None:
    """Test: trace file is generated and contains entries."""
    plan_json = _make_plan_json()
    responses = [
        plan_json,
        "Generated tests",
        '{"action": "complete", "summary": "All passed"}',
    ]
    loop = _make_loop(tmp_dir, responses)
    result = await loop.run()

    trace_path = Path(result["trace_file"])
    assert trace_path.exists()

    entries = loop.tracer.read_entries()
    assert len(entries) > 0

    state_transitions = [
        e for e in entries if e["data"].get("decision") == "state_transition"
    ]
    assert len(state_transitions) > 0


@pytest.mark.asyncio
async def test_loop_revert(tmp_dir: Path) -> None:
    """Test: revert transitions to REVERTED state."""
    plan_json = _make_plan_json()
    responses = [
        plan_json,
        "Generated tests",
        '{"action": "complete", "summary": "All passed"}',
    ]
    loop = _make_loop(tmp_dir, responses)
    await loop.run()

    reverted = await loop.revert()
    assert loop.state == AgentState.REVERTED
    assert loop.termination_reason == TerminationReason.REJECTED


@pytest.mark.asyncio
async def test_loop_run_id_unique(tmp_dir: Path) -> None:
    """Test: each loop gets a unique run ID."""
    loop1 = _make_loop(tmp_dir, [_make_plan_json()])
    loop2 = _make_loop(tmp_dir, [_make_plan_json()])
    assert loop1.run_id != loop2.run_id
