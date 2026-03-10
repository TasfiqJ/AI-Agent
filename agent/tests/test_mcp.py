"""Tests for MCP client and server modules."""

import json
import pytest
from pathlib import Path

from guardian.mcp.client import MCPServerConfig, MCPTool, MCPCallResult, load_mcp_config
from guardian.mcp.server import (
    MCP_TOOLS,
    MCPServer,
    handle_tool_call,
)


# === MCPServerConfig tests ===

def test_mcp_server_config() -> None:
    config = MCPServerConfig(
        name="github",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": "test"},
    )
    assert config.name == "github"
    assert config.command == "npx"
    assert len(config.args) == 2
    assert config.env["GITHUB_TOKEN"] == "test"


def test_mcp_tool() -> None:
    tool = MCPTool(
        name="create_pr",
        description="Create a pull request",
        input_schema={"type": "object", "properties": {}},
        server_name="github",
    )
    assert tool.name == "create_pr"
    assert tool.server_name == "github"


def test_mcp_call_result() -> None:
    result = MCPCallResult(
        content=[{"type": "text", "text": "PR created"}],
        is_error=False,
    )
    assert not result.is_error
    assert result.content[0]["text"] == "PR created"


# === load_mcp_config tests ===

def test_load_mcp_config(tmp_path: Path) -> None:
    config_data = {
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "test-token"},
            },
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"],
            },
        }
    }
    config_file = tmp_path / "mcp.json"
    config_file.write_text(json.dumps(config_data))

    configs = load_mcp_config(str(config_file))
    assert len(configs) == 2
    assert configs[0].name == "github"
    assert configs[0].command == "npx"
    assert configs[0].env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "test-token"
    assert configs[1].name == "filesystem"


def test_load_mcp_config_missing_file() -> None:
    configs = load_mcp_config("/nonexistent/path/mcp.json")
    assert configs == []


def test_load_mcp_config_invalid_json(tmp_path: Path) -> None:
    config_file = tmp_path / "mcp.json"
    config_file.write_text("not json")
    configs = load_mcp_config(str(config_file))
    assert configs == []


def test_load_mcp_config_none() -> None:
    configs = load_mcp_config(None)
    # Should return empty list if no config found at default locations
    assert isinstance(configs, list)


# === MCP Server tool definitions ===

def test_mcp_tools_defined() -> None:
    assert len(MCP_TOOLS) == 3
    names = {t["name"] for t in MCP_TOOLS}
    assert "generate_api_tests" in names
    assert "run_test_suite" in names
    assert "detect_api_framework" in names


def test_mcp_tools_have_schemas() -> None:
    for tool in MCP_TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert "properties" in schema


# === handle_tool_call tests ===

@pytest.mark.asyncio
async def test_handle_detect_framework() -> None:
    """Test detect_api_framework via MCP handler."""
    demo_path = str(Path(__file__).parent.parent.parent / "demo" / "flask-todo-api")
    result = await handle_tool_call("detect_api_framework", {"repo_path": demo_path})

    assert not result["isError"]
    content = json.loads(result["content"][0]["text"])
    assert content["framework"] == "flask"
    assert content["count"] == 6


@pytest.mark.asyncio
async def test_handle_unknown_tool() -> None:
    result = await handle_tool_call("nonexistent_tool", {})
    assert result["isError"]
    assert "Unknown tool" in result["content"][0]["text"]


# === MCPServer message handling ===

@pytest.mark.asyncio
async def test_mcp_server_initialize() -> None:
    server = MCPServer()
    response = await server._handle_message({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1.0"},
        },
    })

    assert response is not None
    assert response["id"] == 1
    result = response["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "test-guardian"


@pytest.mark.asyncio
async def test_mcp_server_tools_list() -> None:
    server = MCPServer()
    response = await server._handle_message({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })

    assert response is not None
    tools = response["result"]["tools"]
    assert len(tools) == 3
    names = {t["name"] for t in tools}
    assert "generate_api_tests" in names


@pytest.mark.asyncio
async def test_mcp_server_notification() -> None:
    server = MCPServer()
    # Notifications have no id and should return None
    response = await server._handle_message({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {},
    })
    assert response is None
    assert server._initialized is True


@pytest.mark.asyncio
async def test_mcp_server_unknown_method() -> None:
    server = MCPServer()
    response = await server._handle_message({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "unknown/method",
        "params": {},
    })

    assert response is not None
    assert "error" in response
    assert response["error"]["code"] == -32601
