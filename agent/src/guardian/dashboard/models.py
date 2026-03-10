"""Pydantic models for dashboard API responses."""

from __future__ import annotations

from pydantic import BaseModel
from typing import Any


class ScanRequest(BaseModel):
    repo_path: str


class ScanResponse(BaseModel):
    framework: str
    endpoints_detected: int
    endpoints: list[dict[str, Any]]
    message: str


class EvalRequest(BaseModel):
    include_external: bool = False


class EvalRepoResponse(BaseModel):
    name: str
    path: str
    framework: str
    expected_endpoints: int
    available: bool


class EvalResultResponse(BaseModel):
    repo_name: str
    framework_detected: str
    framework_correct: bool
    endpoints_expected: int
    endpoints_detected: int
    endpoint_detection_rate: float
    spec_endpoints: int = 0
    spec_match_rate: float = 0.0
    details: dict[str, Any] = {}


class EvalSummaryResponse(BaseModel):
    total_repos: int
    repos_passed: int
    avg_detection_rate: float
    framework_accuracy: float
    results: list[EvalResultResponse]


class RunStartRequest(BaseModel):
    repo_path: str
    permission_mode: str = "trust"
    max_iterations: int = 3
    model: str = "qwen2.5-coder:7b"


class RunStartResponse(BaseModel):
    run_id: str
    message: str


class RunHistoryEntry(BaseModel):
    run_id: str
    repo_path: str
    started_at: str
    completed_at: str | None = None
    state: str
    framework: str | None = None
    endpoints_detected: int = 0
    iterations: int = 0
    files_changed: list[str] = []
    termination_reason: str | None = None


class HistoryResponse(BaseModel):
    runs: list[RunHistoryEntry]


class ScanHistoryEntry(BaseModel):
    timestamp: str
    repo_path: str
    framework: str
    endpoints_detected: int
    endpoints: list[dict[str, Any]]
