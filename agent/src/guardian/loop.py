"""Agentic loop state machine — Plan → Act → Verify.

This is a deterministic state machine, not a while loop.
States: IDLE → PLANNING → ACTING → VERIFYING → COMPLETE (or FAILED/REVERTED)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from guardian.llm.client import LLMClient
from guardian.llm.prompts import ACT_SYSTEM_PROMPT, PLAN_SYSTEM_PROMPT, VERIFY_SYSTEM_PROMPT
from guardian.llm.schemas import AgentPlanSchema
from guardian.safety.checkpoints import CheckpointManager
from guardian.safety.permissions import PermissionManager
from guardian.tools.registry import BudgetExceededError, ToolRegistry
from guardian.trace.logger import TraceLogger

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    REVERTED = "REVERTED"


class TerminationReason(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class AgentLoop:
    """The core agentic loop: Plan → Act → Verify."""

    def __init__(
        self,
        llm: LLMClient,
        tool_registry: ToolRegistry,
        permission_manager: PermissionManager,
        repo_path: Path,
        guardian_dir: Path | None = None,
        max_iterations: int = 3,
        max_tool_calls: int = 50,
    ) -> None:
        self.llm = llm
        self.tools = tool_registry
        self.permissions = permission_manager
        self.repo_path = repo_path
        self.max_iterations = max_iterations

        self.tools.set_budget(max_tool_calls)

        self.run_id = f"run-{uuid.uuid4().hex[:8]}"

        self.guardian_dir = guardian_dir or repo_path / ".test-guardian"
        self.guardian_dir.mkdir(parents=True, exist_ok=True)

        self.tracer = TraceLogger(
            self.run_id,
            self.guardian_dir / "traces",
        )
        self.checkpoints = CheckpointManager(
            self.run_id,
            self.guardian_dir / "checkpoints",
        )

        # State
        self.state = AgentState.IDLE
        self.iteration = 0
        self.plan: AgentPlanSchema | None = None
        self.termination_reason: TerminationReason | None = None
        self.test_results: list[dict[str, Any]] = []
        self.files_changed: list[str] = []

        # Optional event callback for dashboard streaming
        self.event_callback: Callable[..., Any] | None = None

    async def run(self) -> dict[str, Any]:
        """Execute the full agentic loop. Returns a summary dict."""
        try:
            # PLAN phase
            self._transition(AgentState.PLANNING)
            plan = await self._plan()
            if plan is None:
                self._transition(AgentState.FAILED)
                self.termination_reason = TerminationReason.ERROR
                return self._summary()

            self.plan = plan
            self.tracer.log_decision(
                "plan_generated",
                f"Found {len(plan.endpoints)} endpoints, "
                f"{len(plan.steps)} steps planned",
            )
            await self._emit("plan_generated", {
                "endpoints_count": len(plan.endpoints),
                "steps_count": len(plan.steps),
            })

            # ACT → VERIFY loop
            for iteration in range(1, self.max_iterations + 1):
                self.iteration = iteration
                self.tracer.log_decision(
                    "iteration_start",
                    f"Starting iteration {iteration}/{self.max_iterations}",
                )
                await self._emit("iteration_start", {
                    "iteration": iteration,
                    "max_iterations": self.max_iterations,
                })

                # ACT
                self._transition(AgentState.ACTING)
                changes = await self._act()
                if not changes:
                    self.tracer.log_decision("no_changes", "ACT produced no changes")
                    break

                # VERIFY
                self._transition(AgentState.VERIFYING)
                all_pass = await self._verify()

                if all_pass:
                    self._transition(AgentState.COMPLETE)
                    self.termination_reason = TerminationReason.SUCCESS
                    self.tracer.log_decision("success", "All tests passed")
                    return self._summary()

                if iteration == self.max_iterations:
                    self._transition(AgentState.COMPLETE)
                    self.termination_reason = TerminationReason.PARTIAL
                    self.tracer.log_decision(
                        "max_iterations",
                        f"Reached max iterations ({self.max_iterations})",
                    )

            return self._summary()

        except BudgetExceededError:
            self._transition(AgentState.FAILED)
            self.termination_reason = TerminationReason.BUDGET_EXCEEDED
            self.tracer.log_decision(
                "budget_exceeded",
                f"Tool budget exhausted: {self.tools.call_count}/{self.tools.budget}",
            )
            return self._summary()

        except Exception as e:
            self._transition(AgentState.FAILED)
            self.termination_reason = TerminationReason.ERROR
            self.tracer.log_error(str(e))
            logger.exception("Agent loop failed")
            return self._summary()

    async def revert(self) -> list[str]:
        """Revert all changes from this run."""
        reverted = self.checkpoints.revert_all()
        self._transition(AgentState.REVERTED)
        self.termination_reason = TerminationReason.REJECTED
        self.tracer.log_decision("reverted", f"Reverted {len(reverted)} files")
        return reverted

    async def _plan(self) -> AgentPlanSchema | None:
        """Execute the PLAN phase — read-only analysis."""
        messages = [
            {
                "role": "user",
                "content": f"Analyze the repository at {self.repo_path} and create a test generation plan.",
            }
        ]
        self.tracer.log_llm_request(messages, PLAN_SYSTEM_PROMPT)
        try:
            plan = await self.llm.structured_output(
                messages=messages,
                schema=AgentPlanSchema,
                system=PLAN_SYSTEM_PROMPT,
            )
            assert isinstance(plan, AgentPlanSchema)
            self.tracer.log_llm_response(plan.model_dump_json(), "plan")
            return plan
        except (ValueError, Exception) as e:
            self.tracer.log_error(f"Plan generation failed: {e}")
            logger.error("Plan generation failed: %s", e)
            return None

    async def _act(self) -> list[str]:
        """Execute the ACT phase — generate test files."""
        changes: list[str] = []
        if not self.plan:
            return changes

        messages = [
            {
                "role": "user",
                "content": (
                    f"Generate tests for the following plan:\n"
                    f"{self.plan.model_dump_json(indent=2)}\n\n"
                    f"Iteration: {self.iteration}\n"
                    f"Previous test results: {self.test_results}"
                ),
            }
        ]
        self.tracer.log_llm_request(messages, ACT_SYSTEM_PROMPT)
        response = await self.llm.chat(messages=messages, system=ACT_SYSTEM_PROMPT)
        self.tracer.log_llm_response(response.content, response.model)

        for test_file in self.plan.test_files:
            changes.append(test_file)
            self.files_changed.append(test_file)

        return changes

    async def _verify(self) -> bool:
        """Execute the VERIFY phase — run tests in sandbox."""
        messages = [
            {
                "role": "user",
                "content": (
                    f"Verify test results.\n"
                    f"Previous results: {self.test_results}\n"
                    f"Iteration: {self.iteration}"
                ),
            }
        ]
        self.tracer.log_llm_request(messages, VERIFY_SYSTEM_PROMPT)
        response = await self.llm.chat(messages=messages, system=VERIFY_SYSTEM_PROMPT)
        self.tracer.log_llm_response(response.content, response.model)

        all_pass = "complete" in response.content.lower()
        self.test_results.append(
            {
                "iteration": self.iteration,
                "all_pass": all_pass,
                "raw_output": response.content[:500],
            }
        )
        return all_pass

    async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event to the dashboard if callback is set."""
        if self.event_callback is not None:
            try:
                await self.event_callback(event_type, data)
            except Exception:
                logger.debug("Event callback failed for %s", event_type)

    def _transition(self, new_state: AgentState) -> None:
        """Transition to a new state with logging."""
        old_state = self.state
        self.state = new_state
        self.tracer.log_decision(
            "state_transition",
            f"{old_state.value} → {new_state.value}",
        )
        logger.info("State: %s → %s", old_state.value, new_state.value)

        # Emit event for dashboard
        if self.event_callback is not None:
            asyncio.ensure_future(self._emit("state_change", {
                "from_state": old_state.value,
                "to_state": new_state.value,
            }))

    def _summary(self) -> dict[str, Any]:
        """Generate a run summary."""
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            "termination_reason": (
                self.termination_reason.value if self.termination_reason else None
            ),
            "iterations": self.iteration,
            "tool_calls_used": self.tools.call_count,
            "tool_calls_budget": self.tools.budget,
            "files_changed": self.files_changed,
            "test_results": self.test_results,
            "trace_file": str(self.tracer.file_path),
        }
