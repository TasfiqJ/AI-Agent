"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from guardian.llm.schemas import (
    AgentPlanSchema,
    EndpointInfo,
    FileDiffSchema,
    PlanStepSchema,
    TestFixSchema,
    ToolCallRequestSchema,
)


def test_endpoint_info_valid() -> None:
    ep = EndpointInfo(
        method="GET",
        path="/api/users",
        handler="get_users",
        file="app.py",
        line=10,
    )
    assert ep.method == "GET"
    assert ep.path == "/api/users"


def test_endpoint_info_missing_field() -> None:
    with pytest.raises(ValidationError):
        EndpointInfo(method="GET", path="/api/users")  # type: ignore[call-arg]


def test_agent_plan_schema() -> None:
    plan = AgentPlanSchema(
        framework="flask",
        endpoints=[
            EndpointInfo(
                method="GET",
                path="/api/todos",
                handler="get_todos",
                file="app.py",
                line=15,
            )
        ],
        steps=[
            PlanStepSchema(
                id=1,
                description="Generate test file",
                tool_calls=["file_write"],
                output_file="tests/test_todos.py",
            )
        ],
        test_files=["tests/test_todos.py"],
        success_criteria=["All tests pass"],
    )
    assert plan.framework == "flask"
    assert len(plan.endpoints) == 1
    assert len(plan.steps) == 1


def test_tool_call_request() -> None:
    req = ToolCallRequestSchema(
        tool="file_read",
        params={"path": "app.py"},
    )
    assert req.tool == "file_read"


def test_file_diff_schema() -> None:
    diff = FileDiffSchema(
        path="tests/test_api.py",
        diff="--- /dev/null\n+++ tests/test_api.py\n@@ -0,0 +1 @@\n+import pytest",
        is_new=True,
    )
    assert diff.is_new is True


def test_test_fix_schema() -> None:
    fix = TestFixSchema(
        file="tests/test_api.py",
        diff="@@ -5,1 +5,1 @@\n-assert resp.status == 200\n+assert resp.status_code == 200",
        reason="Wrong attribute name for response status",
    )
    assert "status_code" in fix.diff
