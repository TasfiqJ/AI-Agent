"""Tool registry — register tools with JSON Schema definitions.

Tools are discovered by schema, not by hardcoded function name.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """A registered tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    execute: Callable[..., Awaitable[Any]]
    phase: list[str] = field(default_factory=lambda: ["plan", "act"])
    requires_approval: bool = False


class ToolRegistry:
    """Registry for agent tools. Supports JSON Schema discovery."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._call_count: int = 0
        self._budget: int = 50

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def budget(self) -> int:
        return self._budget

    @property
    def budget_remaining(self) -> int:
        return max(0, self._budget - self._call_count)

    def set_budget(self, budget: int) -> None:
        self._budget = budget

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            logger.warning("Tool %s already registered, overwriting", tool.name)
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, phase: str | None = None) -> list[ToolDefinition]:
        """List all registered tools, optionally filtered by phase."""
        tools = list(self._tools.values())
        if phase:
            tools = [t for t in tools if phase in t.phase]
        return tools

    def get_schemas(self, phase: str | None = None) -> list[dict[str, Any]]:
        """Get JSON Schema definitions for all tools (for LLM tool-use)."""
        schemas = []
        for tool in self.list_tools(phase):
            schemas.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            )
        return schemas

    async def execute(
        self, name: str, params: dict[str, Any]
    ) -> Any:
        """Execute a tool by name with parameters."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        if self._call_count >= self._budget:
            raise BudgetExceededError(
                f"Tool budget exceeded: {self._call_count}/{self._budget}"
            )

        self._call_count += 1
        logger.info(
            "Executing tool %s (%d/%d)",
            name,
            self._call_count,
            self._budget,
        )

        result = await tool.execute(**params)
        return result

    def reset_count(self) -> None:
        """Reset the tool call counter."""
        self._call_count = 0


class BudgetExceededError(Exception):
    """Raised when the tool call budget is exceeded."""
