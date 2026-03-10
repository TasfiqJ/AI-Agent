"""Dashboard API routes and HTML serving."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from guardian.dashboard.models import (
    EvalRepoResponse,
    EvalRequest,
    EvalResultResponse,
    EvalSummaryResponse,
    RunStartRequest,
    RunStartResponse,
    ScanRequest,
    ScanResponse,
)
from guardian.dashboard.state import dashboard_state
from guardian.eval.harness import DEMO_REPOS, EXTERNAL_REPOS, evaluate_all, evaluate_full
from guardian.tools.code_intel import detect_framework, extract_endpoints

logger = logging.getLogger(__name__)

router = APIRouter()

# Templates directory
_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# Project root (AI-Agent directory)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


def _resolve_path(raw_path: str) -> str:
    """Resolve relative paths (./demo/...) against the project root."""
    if raw_path.startswith("./") or raw_path.startswith(".\\"):
        return str((_PROJECT_ROOT / raw_path).resolve())
    return raw_path


# ── HTML Page ──────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request) -> HTMLResponse:
    """Serve the main dashboard page."""
    return templates.TemplateResponse(request, "index.html")


# ── API Endpoints ──────────────────────────────────────────


@router.get("/api/ping")
async def ping() -> dict[str, Any]:
    """Lightweight connection check."""
    return {
        "pong": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/browse")
async def browse_folders(path: str = "") -> dict[str, Any]:
    """List folders at a given path for the folder picker."""
    import os
    import string

    # Default: show drive letters on Windows, / on Linux/Mac
    if not path:
        if os.name == "nt":
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append({"name": f"{letter}:", "path": drive, "type": "drive"})
            return {"current": "", "parent": "", "items": drives}
        else:
            path = "/"

    target = Path(path)
    if not target.exists() or not target.is_dir():
        return {"current": path, "parent": str(target.parent), "items": [], "error": "Not found"}

    items = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "folder",
                })
    except PermissionError:
        return {"current": str(target), "parent": str(target.parent), "items": [], "error": "Permission denied"}

    return {
        "current": str(target),
        "parent": str(target.parent) if target.parent != target else "",
        "items": items,
    }


@router.post("/api/scan", response_model=ScanResponse)
async def scan_project(req: ScanRequest) -> ScanResponse:
    """Scan a project for framework and endpoints."""
    repo_path = _resolve_path(req.repo_path)
    framework = await detect_framework(repo_path)
    endpoints = await extract_endpoints(repo_path, framework)

    dashboard_state.record_scan(
        repo_path=repo_path,
        framework=framework,
        endpoints_detected=len(endpoints),
        endpoints=endpoints,
    )

    return ScanResponse(
        framework=framework,
        endpoints_detected=len(endpoints),
        endpoints=endpoints,
        message=f"Detected {framework} with {len(endpoints)} endpoints",
    )


@router.post("/api/eval", response_model=EvalSummaryResponse)
async def run_evaluation(req: EvalRequest) -> EvalSummaryResponse:
    """Run evaluation harness against repos."""
    project_root = str(_PROJECT_ROOT)

    if req.include_external:
        summary = await evaluate_full(project_root)
    else:
        summary = await evaluate_all(project_root)

    results = [
        EvalResultResponse(
            repo_name=r.repo_name,
            framework_detected=r.framework_detected,
            framework_correct=r.framework_correct,
            endpoints_expected=r.endpoints_expected,
            endpoints_detected=r.endpoints_detected,
            endpoint_detection_rate=r.endpoint_detection_rate,
            spec_endpoints=r.spec_endpoints,
            spec_match_rate=r.spec_match_rate,
            details=r.details,
        )
        for r in summary.results
    ]

    return EvalSummaryResponse(
        total_repos=summary.total_repos,
        repos_passed=summary.repos_passed,
        avg_detection_rate=summary.avg_detection_rate,
        framework_accuracy=summary.framework_accuracy,
        results=results,
    )


@router.get("/api/eval/repos", response_model=list[EvalRepoResponse])
async def list_eval_repos() -> list[EvalRepoResponse]:
    """List available evaluation repos."""
    repos = []
    project_root = _PROJECT_ROOT

    for demo in DEMO_REPOS + EXTERNAL_REPOS:
        if demo.absolute:
            available = Path(demo.path).exists()
        else:
            available = (project_root / demo.path).exists()

        repos.append(
            EvalRepoResponse(
                name=demo.name,
                path=demo.path,
                framework=demo.framework,
                expected_endpoints=demo.expected_endpoints,
                available=available,
            )
        )

    return repos


@router.get("/api/history")
async def get_history() -> dict[str, Any]:
    """Get run and scan history."""
    return {
        "runs": [r.model_dump() for r in dashboard_state.run_history],
        "scans": [s.model_dump() for s in dashboard_state.scan_history],
    }


@router.post("/api/run/start", response_model=RunStartResponse)
async def start_run(req: RunStartRequest) -> RunStartResponse:
    """Start an agent run and return run_id for SSE streaming."""
    from guardian.llm.client import MockLLMClient
    from guardian.loop import AgentLoop
    from guardian.safety.permissions import PermissionManager
    from guardian.tools.registry import ToolRegistry

    # Create components
    llm = MockLLMClient()
    tool_registry = ToolRegistry()
    perm_mode = req.permission_mode
    permission_manager = PermissionManager(mode=perm_mode)
    repo_path = Path(_resolve_path(req.repo_path))

    # Create event queue
    loop = AgentLoop(
        llm=llm,
        tool_registry=tool_registry,
        permission_manager=permission_manager,
        repo_path=repo_path,
        max_iterations=req.max_iterations,
    )

    run_id = loop.run_id
    queue = dashboard_state.create_event_queue(run_id)

    # Event callback that pushes to the queue
    async def on_event(event_type: str, data: dict[str, Any]) -> None:
        await queue.put((event_type, data))

    loop.event_callback = on_event

    # Run the loop in a background task
    started_at = datetime.now(timezone.utc).isoformat()

    async def run_and_record() -> None:
        try:
            summary = await loop.run()
            await queue.put(("run_complete", summary))
            dashboard_state.record_run(run_id, req.repo_path, started_at, summary)
        except Exception as e:
            await queue.put(("error", {"error": str(e)}))
        finally:
            await queue.put(("stream_end", {}))

    task = asyncio.create_task(run_and_record())
    dashboard_state.active_tasks[run_id] = task

    return RunStartResponse(run_id=run_id, message="Run started")


@router.get("/api/run/events/{run_id}")
async def run_events(run_id: str) -> StreamingResponse:
    """SSE stream for a running agent."""
    queue = dashboard_state.event_queues.get(run_id)

    if queue is None:
        async def not_found() -> Any:
            yield f"event: error\ndata: {{\"error\": \"Run {run_id} not found\"}}\n\n"

        return StreamingResponse(
            not_found(),
            media_type="text/event-stream",
        )

    async def event_stream() -> Any:
        import json

        while True:
            try:
                event_type, data = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue

            if event_type == "stream_end":
                dashboard_state.remove_event_queue(run_id)
                break

            yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
