"""MCP Server — expose test-guardian tools for other agents.

Implements the MCP server protocol so other agents can:
  - Call generate_api_tests to generate tests for a repository
  - Call run_test_suite to run existing tests in a sandbox
  - Discover available tools via MCP tool listing

Run as: python -m guardian.mcp.server
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from guardian.llm.client import create_llm_client
from guardian.loop import AgentLoop
from guardian.safety.permissions import PermissionManager, PermissionMode
from guardian.tools.code_intel import detect_framework, extract_endpoints
from guardian.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Tool definitions for MCP
MCP_TOOLS = [
    {
        "name": "generate_api_tests",
        "description": (
            "Generate API tests for a repository. Detects the framework "
            "(Flask, FastAPI, Express), extracts endpoints, and generates "
            "comprehensive test files using an agentic Plan→Act→Verify loop."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to generate tests for.",
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum iterations for the agent loop.",
                    "default": 3,
                },
                "model": {
                    "type": "string",
                    "description": "LLM model to use.",
                    "default": "qwen2.5-coder:7b",
                },
            },
            "required": ["repo_path"],
        },
    },
    {
        "name": "run_test_suite",
        "description": (
            "Run the test suite in a sandboxed Docker container. "
            "Returns pass/fail results with error details."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository containing tests.",
                },
                "test_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific test files to run. Runs all if omitted.",
                },
                "runner": {
                    "type": "string",
                    "enum": ["pytest", "jest"],
                    "description": "Test runner to use.",
                    "default": "pytest",
                },
            },
            "required": ["repo_path"],
        },
    },
    {
        "name": "detect_api_framework",
        "description": (
            "Detect the API framework used in a repository and list endpoints."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to analyze.",
                },
            },
            "required": ["repo_path"],
        },
    },
]


async def handle_tool_call(
    tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Handle an MCP tool call and return the result."""

    if tool_name == "generate_api_tests":
        return await _handle_generate_tests(arguments)
    elif tool_name == "run_test_suite":
        return await _handle_run_tests(arguments)
    elif tool_name == "detect_api_framework":
        return await _handle_detect_framework(arguments)
    else:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True,
        }


async def _handle_generate_tests(args: dict[str, Any]) -> dict[str, Any]:
    """Generate API tests using the agentic loop."""
    repo_path = args["repo_path"]
    max_iterations = args.get("max_iterations", 3)
    model = args.get("model", "qwen2.5-coder:7b")

    try:
        from pathlib import Path

        llm = create_llm_client(model=model)
        registry = ToolRegistry()
        perms = PermissionManager(mode=PermissionMode.TRUST)

        loop = AgentLoop(
            llm=llm,
            tool_registry=registry,
            permission_manager=perms,
            repo_path=Path(repo_path),
            max_iterations=max_iterations,
        )

        result = await loop.run()

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, indent=2, default=str),
            }],
            "isError": False,
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "isError": True,
        }


async def _handle_run_tests(args: dict[str, Any]) -> dict[str, Any]:
    """Run tests in a Docker sandbox."""
    repo_path = args["repo_path"]
    test_files = args.get("test_files")
    runner = args.get("runner", "pytest")

    try:
        from guardian.sandbox.runner import run_pytest, run_jest, detect_test_runner
        from guardian.sandbox.result_parser import parse_test_output

        if runner == "auto":
            runner = detect_test_runner(repo_path)

        if runner == "pytest":
            result = await run_pytest(repo_path, test_files=test_files)
        else:
            result = await run_jest(repo_path, test_files=test_files)

        parsed = parse_test_output(result.stdout, runner)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "exit_code": result.exit_code,
                    "passed": parsed.passed,
                    "failed": parsed.failed,
                    "total": parsed.total,
                    "all_passed": parsed.all_passed,
                    "duration_ms": result.duration_ms,
                    "stdout": result.stdout[:2000],
                    "stderr": result.stderr[:500],
                }, indent=2),
            }],
            "isError": False,
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "isError": True,
        }


async def _handle_detect_framework(args: dict[str, Any]) -> dict[str, Any]:
    """Detect API framework and extract endpoints."""
    repo_path = args["repo_path"]

    try:
        framework = await detect_framework(repo_path)
        endpoints = await extract_endpoints(repo_path, framework)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "framework": framework,
                    "endpoints": endpoints,
                    "count": len(endpoints),
                }, indent=2, default=str),
            }],
            "isError": False,
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {e}"}],
            "isError": True,
        }


class MCPServer:
    """stdio-based MCP server that handles JSON-RPC messages."""

    def __init__(self) -> None:
        self._initialized = False

    async def run(self) -> None:
        """Main server loop — read JSON-RPC from stdin, write to stdout."""
        logger.info("MCP server starting...")

        while True:
            try:
                message = self._read_message()
                if message is None:
                    break

                response = await self._handle_message(message)
                if response is not None:
                    self._write_message(response)

            except Exception as e:
                logger.exception("MCP server error: %s", e)
                break

        logger.info("MCP server stopped")

    async def _handle_message(
        self, message: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Handle a JSON-RPC message and return a response (or None for notifications)."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        # Notifications (no id) don't get a response
        if msg_id is None:
            if method == "notifications/initialized":
                self._initialized = True
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "test-guardian",
                        "version": "0.1.0",
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": MCP_TOOLS},
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = await handle_tool_call(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result,
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    def _read_message(self) -> dict[str, Any] | None:
        """Read a JSON-RPC message from stdin."""
        try:
            header = b""
            while True:
                byte = sys.stdin.buffer.read(1)
                if not byte:
                    return None
                header += byte
                if header.endswith(b"\r\n\r\n"):
                    break

            header_str = header.decode("utf-8")
            parts = header_str.split("Content-Length: ")
            if len(parts) < 2:
                return None

            content_length = int(parts[1].split("\r\n")[0])
            body = sys.stdin.buffer.read(content_length)
            return json.loads(body.decode("utf-8"))

        except (ValueError, json.JSONDecodeError, OSError):
            return None

    def _write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to stdout."""
        body = json.dumps(message)
        header = f"Content-Length: {len(body)}\r\n\r\n"
        sys.stdout.buffer.write(header.encode() + body.encode())
        sys.stdout.buffer.flush()


def main() -> None:
    """Entry point for running as MCP server."""
    server = MCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
