"""MCP Client — connect to external MCP servers (e.g., GitHub) for tool discovery.

Implements the MCP client protocol to:
  - Discover tools from MCP servers at startup
  - Call MCP tools (e.g., create PR via GitHub MCP)
  - Register discovered tools in the agent's ToolRegistry
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for connecting to an MCP server."""

    name: str
    command: str  # e.g., "npx"
    args: list[str] = field(default_factory=list)  # e.g., ["-y", "@modelcontextprotocol/server-github"]
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPTool:
    """A tool discovered from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str


@dataclass
class MCPCallResult:
    """Result from calling an MCP tool."""

    content: list[dict[str, Any]]
    is_error: bool = False


class MCPClient:
    """Client for communicating with MCP servers via stdio transport.

    Uses JSON-RPC over stdin/stdout to communicate with MCP server processes.
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self._process: subprocess.Popen[bytes] | None = None
        self._request_id = 0
        self._tools: list[MCPTool] = []

    async def connect(self) -> bool:
        """Start the MCP server process and initialize the connection."""
        try:
            env = dict(**self.config.env)
            cmd = [self.config.command] + self.config.args

            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env if env else None,
            )

            # Send initialize request
            result = self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-guardian",
                    "version": "0.1.0",
                },
            })

            if result is None:
                logger.error("Failed to initialize MCP server: %s", self.config.name)
                return False

            # Send initialized notification
            self._send_notification("notifications/initialized", {})

            logger.info("Connected to MCP server: %s", self.config.name)
            return True

        except (FileNotFoundError, OSError) as e:
            logger.error("Failed to start MCP server %s: %s", self.config.name, e)
            return False

    async def discover_tools(self) -> list[MCPTool]:
        """List available tools from the MCP server."""
        result = self._send_request("tools/list", {})
        if result is None:
            return []

        tools = []
        for tool_data in result.get("tools", []):
            tool = MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
                server_name=self.config.name,
            )
            tools.append(tool)

        self._tools = tools
        logger.info(
            "Discovered %d tools from %s: %s",
            len(tools),
            self.config.name,
            [t.name for t in tools],
        )
        return tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> MCPCallResult:
        """Call a tool on the MCP server."""
        result = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        if result is None:
            return MCPCallResult(
                content=[{"type": "text", "text": "MCP call failed"}],
                is_error=True,
            )

        return MCPCallResult(
            content=result.get("content", []),
            is_error=result.get("isError", False),
        )

    async def disconnect(self) -> None:
        """Shut down the MCP server process."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            logger.info("Disconnected from MCP server: %s", self.config.name)

    def _send_request(
        self, method: str, params: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Send a JSON-RPC request and return the result."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            return None

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        try:
            message = json.dumps(request)
            self._process.stdin.write(
                f"Content-Length: {len(message)}\r\n\r\n{message}".encode()
            )
            self._process.stdin.flush()

            # Read response
            response_data = self._read_response()
            if response_data and "result" in response_data:
                return response_data["result"]
            if response_data and "error" in response_data:
                logger.error("MCP error: %s", response_data["error"])
            return None

        except (BrokenPipeError, OSError) as e:
            logger.error("MCP communication error: %s", e)
            return None

    def _send_notification(
        self, method: str, params: dict[str, Any]
    ) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }

        try:
            message = json.dumps(notification)
            self._process.stdin.write(
                f"Content-Length: {len(message)}\r\n\r\n{message}".encode()
            )
            self._process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def _read_response(self) -> dict[str, Any] | None:
        """Read a JSON-RPC response from stdout."""
        if not self._process or not self._process.stdout:
            return None

        try:
            # Read Content-Length header
            header = b""
            while True:
                byte = self._process.stdout.read(1)
                if not byte:
                    return None
                header += byte
                if header.endswith(b"\r\n\r\n"):
                    break

            header_str = header.decode("utf-8")
            length_match = header_str.split("Content-Length: ")
            if len(length_match) < 2:
                return None

            content_length = int(length_match[1].split("\r\n")[0])
            body = self._process.stdout.read(content_length)
            return json.loads(body.decode("utf-8"))

        except (ValueError, json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read MCP response: %s", e)
            return None


def load_mcp_config(config_path: str | Path | None = None) -> list[MCPServerConfig]:
    """Load MCP server configurations from a JSON file.

    Expected format (compatible with Claude Desktop):
    {
        "mcpServers": {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "..."}
            }
        }
    }
    """
    if config_path is None:
        # Look for config in common locations
        candidates = [
            Path.cwd() / ".test-guardian" / "mcp.json",
            Path.home() / ".config" / "test-guardian" / "mcp.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break

    if config_path is None:
        return []

    path = Path(config_path)
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = data.get("mcpServers", {})

        configs = []
        for name, server_data in servers.items():
            configs.append(MCPServerConfig(
                name=name,
                command=server_data["command"],
                args=server_data.get("args", []),
                env=server_data.get("env", {}),
            ))
        return configs

    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse MCP config: %s", e)
        return []
