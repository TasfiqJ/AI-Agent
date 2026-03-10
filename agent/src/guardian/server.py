"""FastAPI server — the HTTP interface between CLI and agent backend.

Provides:
  - /health          — health check
  - /init            — detect framework + endpoints
  - /run             — start agentic loop (SSE stream)
  - /status          — get current run status
  - /revert          — revert all changes from a run
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from guardian.llm.client import create_llm_client
from guardian.loop import AgentLoop, AgentState, TerminationReason
from guardian.safety.permissions import PermissionManager, PermissionMode
from guardian.tools.code_intel import detect_framework, extract_endpoints
from guardian.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

app = FastAPI(
    title="test-guardian agent",
    version="0.1.0",
    description="Agentic backend for API test generation",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount dashboard
from guardian.dashboard.routes import router as dashboard_router

app.include_router(dashboard_router, prefix="/dashboard")

_dashboard_static = Path(__file__).parent / "dashboard" / "static"
if _dashboard_static.exists():
    app.mount(
        "/dashboard/static",
        StaticFiles(directory=str(_dashboard_static)),
        name="dashboard-static",
    )

# In-memory store for the current/last run
_current_loop: AgentLoop | None = None
_last_result: dict[str, Any] | None = None


# === Models ===

class HealthResponse(BaseModel):
    status: str
    version: str


class InitRequest(BaseModel):
    repo_path: str


class InitResponse(BaseModel):
    framework: str
    endpoints_detected: int
    endpoints: list[dict[str, Any]]
    message: str


class RunRequest(BaseModel):
    repo_path: str
    permission_mode: str = "default"
    max_iterations: int = 3
    max_tool_calls: int = 50
    model: str = "qwen2.5-coder:7b"


class StatusResponse(BaseModel):
    run_id: str | None
    state: str
    termination_reason: str | None
    iteration: int
    tool_calls_used: int
    tool_calls_budget: int
    files_changed: list[str]
    test_results: list[dict[str, Any]]


class RevertRequest(BaseModel):
    run_id: str | None = None


class RevertResponse(BaseModel):
    reverted_files: list[str]
    message: str


# === Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/init", response_model=InitResponse)
async def init_repo(req: InitRequest) -> InitResponse:
    """Initialize guardian for a repository. Detects framework and endpoints."""
    framework = await detect_framework(req.repo_path)
    endpoints = await extract_endpoints(req.repo_path, framework)

    return InitResponse(
        framework=framework,
        endpoints_detected=len(endpoints),
        endpoints=endpoints,
        message=f"Detected {framework} framework with {len(endpoints)} endpoints",
    )


@app.post("/run")
async def run_agent(req: RunRequest) -> StreamingResponse:
    """Start the agentic loop. Returns SSE stream of progress events."""

    async def event_stream() -> Any:
        global _current_loop, _last_result

        try:
            # Create the agent loop
            mode = PermissionMode(req.permission_mode)
            llm = create_llm_client(model=req.model)
            registry = ToolRegistry()
            perms = PermissionManager(mode=mode)

            from pathlib import Path
            repo_path = Path(req.repo_path)
            guardian_dir = repo_path / ".test-guardian"

            loop = AgentLoop(
                llm=llm,
                tool_registry=registry,
                permission_manager=perms,
                repo_path=repo_path,
                guardian_dir=guardian_dir,
                max_iterations=req.max_iterations,
                max_tool_calls=req.max_tool_calls,
            )
            _current_loop = loop

            # Send start event
            yield _sse_event("run_start", {
                "run_id": loop.run_id,
                "repo_path": req.repo_path,
                "permission_mode": req.permission_mode,
            })

            # Run the loop
            result = await loop.run()
            _last_result = result

            # Send completion event
            yield _sse_event("run_complete", result)

        except Exception as e:
            logger.exception("Agent run failed")
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    """Get the status of the current or last run."""
    if _current_loop is None:
        return StatusResponse(
            run_id=None,
            state="IDLE",
            termination_reason=None,
            iteration=0,
            tool_calls_used=0,
            tool_calls_budget=50,
            files_changed=[],
            test_results=[],
        )

    loop = _current_loop
    return StatusResponse(
        run_id=loop.run_id,
        state=loop.state.value,
        termination_reason=(
            loop.termination_reason.value if loop.termination_reason else None
        ),
        iteration=loop.iteration,
        tool_calls_used=loop.tools.call_count,
        tool_calls_budget=loop.tools.budget,
        files_changed=loop.files_changed,
        test_results=loop.test_results,
    )


@app.post("/revert", response_model=RevertResponse)
async def revert(req: RevertRequest) -> RevertResponse:
    """Revert all changes from the current or specified run."""
    if _current_loop is None:
        return RevertResponse(
            reverted_files=[],
            message="No active run to revert",
        )

    reverted = await _current_loop.revert()
    return RevertResponse(
        reverted_files=reverted,
        message=f"Reverted {len(reverted)} files",
    )


def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Event message."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"
