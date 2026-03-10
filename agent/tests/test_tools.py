"""Tests for the tool registry."""

import pytest

from guardian.tools.registry import BudgetExceededError, ToolDefinition, ToolRegistry


async def mock_file_read(path: str) -> str:
    return f"Contents of {path}"


async def mock_file_write(path: str, diff: str) -> str:
    return f"Applied diff to {path}"


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        ToolDefinition(
            name="file_read",
            description="Read file contents",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            execute=mock_file_read,
            phase=["plan", "act"],
            requires_approval=False,
        )
    )
    reg.register(
        ToolDefinition(
            name="file_write",
            description="Write file via unified diff",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "diff": {"type": "string"},
                },
                "required": ["path", "diff"],
            },
            execute=mock_file_write,
            phase=["act"],
            requires_approval=True,
        )
    )
    return reg


def test_registry_register_and_get(registry: ToolRegistry) -> None:
    tool = registry.get("file_read")
    assert tool is not None
    assert tool.name == "file_read"


def test_registry_list_all(registry: ToolRegistry) -> None:
    tools = registry.list_tools()
    assert len(tools) == 2


def test_registry_list_by_phase(registry: ToolRegistry) -> None:
    plan_tools = registry.list_tools(phase="plan")
    assert len(plan_tools) == 1
    assert plan_tools[0].name == "file_read"

    act_tools = registry.list_tools(phase="act")
    assert len(act_tools) == 2


def test_registry_get_schemas(registry: ToolRegistry) -> None:
    schemas = registry.get_schemas()
    assert len(schemas) == 2
    assert all("name" in s and "parameters" in s for s in schemas)


@pytest.mark.asyncio
async def test_registry_execute(registry: ToolRegistry) -> None:
    result = await registry.execute("file_read", {"path": "app.py"})
    assert "Contents of app.py" in result
    assert registry.call_count == 1


@pytest.mark.asyncio
async def test_registry_budget_enforcement(registry: ToolRegistry) -> None:
    registry.set_budget(2)
    await registry.execute("file_read", {"path": "a.py"})
    await registry.execute("file_read", {"path": "b.py"})

    with pytest.raises(BudgetExceededError):
        await registry.execute("file_read", {"path": "c.py"})


@pytest.mark.asyncio
async def test_registry_unknown_tool(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="Unknown tool"):
        await registry.execute("nonexistent", {})


def test_registry_reset_count(registry: ToolRegistry) -> None:
    registry._call_count = 10
    registry.reset_count()
    assert registry.call_count == 0
