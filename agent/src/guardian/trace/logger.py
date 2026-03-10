"""JSON Lines trace logger — every tool call, LLM response, and decision is persisted.

Runs are replayable from trace files.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TraceLogger:
    """Persists trace entries to a JSON Lines file."""

    def __init__(self, run_id: str, trace_dir: Path) -> None:
        self.run_id = run_id
        self.trace_dir = trace_dir
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = trace_dir / f"{run_id}.jsonl"
        self._step = 0

    @property
    def file_path(self) -> Path:
        return self._file_path

    def log(
        self,
        entry_type: str,
        data: dict[str, Any],
    ) -> None:
        """Append a trace entry to the log file."""
        self._step += 1
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "step": self._step,
            "type": entry_type,
            "data": data,
        }
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def log_tool_call(
        self, tool_name: str, params: dict[str, Any], result: Any
    ) -> None:
        """Log a tool execution."""
        self.log(
            "tool_call",
            {
                "tool": tool_name,
                "params": params,
                "result": str(result)[:2000],  # Truncate large results
            },
        )

    def log_llm_request(
        self, messages: list[dict[str, str]], system: str | None
    ) -> None:
        """Log an LLM request."""
        self.log(
            "llm_request",
            {
                "messages": messages[-2:],  # Only last 2 to save space
                "system_prompt_length": len(system) if system else 0,
            },
        )

    def log_llm_response(self, content: str, model: str) -> None:
        """Log an LLM response."""
        self.log(
            "llm_response",
            {
                "content": content[:2000],
                "model": model,
            },
        )

    def log_decision(self, decision: str, reason: str) -> None:
        """Log a state machine decision."""
        self.log(
            "decision",
            {"decision": decision, "reason": reason},
        )

    def log_error(self, error: str, context: dict[str, Any] | None = None) -> None:
        """Log an error."""
        self.log(
            "error",
            {"error": error, "context": context or {}},
        )

    def read_entries(self) -> list[dict[str, Any]]:
        """Read all trace entries from the log file."""
        if not self._file_path.exists():
            return []
        entries = []
        with open(self._file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
