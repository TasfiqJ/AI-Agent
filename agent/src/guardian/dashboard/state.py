"""In-memory state for the dashboard."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from guardian.dashboard.models import RunHistoryEntry, ScanHistoryEntry


class DashboardState:
    """Singleton holding dashboard state in memory."""

    def __init__(self) -> None:
        self.run_history: list[RunHistoryEntry] = []
        self.scan_history: list[ScanHistoryEntry] = []
        self.event_queues: dict[str, asyncio.Queue[tuple[str, dict[str, Any]]]] = {}
        self.active_tasks: dict[str, asyncio.Task[Any]] = {}

    def record_scan(
        self,
        repo_path: str,
        framework: str,
        endpoints_detected: int,
        endpoints: list[dict[str, Any]],
    ) -> None:
        entry = ScanHistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            repo_path=repo_path,
            framework=framework,
            endpoints_detected=endpoints_detected,
            endpoints=endpoints,
        )
        self.scan_history.insert(0, entry)
        # Keep last 50
        if len(self.scan_history) > 50:
            self.scan_history = self.scan_history[:50]

    def record_run(
        self,
        run_id: str,
        repo_path: str,
        started_at: str,
        summary: dict[str, Any],
    ) -> None:
        entry = RunHistoryEntry(
            run_id=run_id,
            repo_path=repo_path,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            state=summary.get("state", "UNKNOWN"),
            framework=summary.get("framework"),
            endpoints_detected=summary.get("endpoints_detected", 0),
            iterations=summary.get("iterations", 0),
            files_changed=summary.get("files_changed", []),
            termination_reason=summary.get("termination_reason"),
        )
        self.run_history.insert(0, entry)
        if len(self.run_history) > 50:
            self.run_history = self.run_history[:50]

    def create_event_queue(self, run_id: str) -> asyncio.Queue[tuple[str, dict[str, Any]]]:
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()
        self.event_queues[run_id] = queue
        return queue

    def remove_event_queue(self, run_id: str) -> None:
        self.event_queues.pop(run_id, None)
        self.active_tasks.pop(run_id, None)


# Global singleton
dashboard_state = DashboardState()
