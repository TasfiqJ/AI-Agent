"""Tests for OpenAPI/Swagger spec parser."""

import json
import pytest
from pathlib import Path

from guardian.tools.spec_parser import openapi_parse


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def _write_openapi3_spec(workspace: Path) -> str:
    """Write a minimal OpenAPI 3.x spec and return the relative path."""
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/api/items": {
                "get": {
                    "operationId": "listItems",
                    "summary": "List items",
                    "parameters": [
                        {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}}
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": {"type": "object"}}
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "createItem",
                    "summary": "Create an item",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            },
                        }
                    },
                    "security": [{"bearerAuth": []}],
                },
            }
        },
    }
    spec_path = workspace / "openapi.json"
    spec_path.write_text(json.dumps(spec))
    return "openapi.json"


def _write_swagger2_spec(workspace: Path) -> str:
    """Write a minimal Swagger 2.x spec and return the relative path."""
    spec = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "getItems",
                    "summary": "Get items",
                    "parameters": [
                        {"name": "page", "in": "query", "type": "integer"}
                    ],
                    "responses": {
                        "200": {
                            "description": "OK",
                            "schema": {"type": "array"},
                        }
                    },
                },
                "post": {
                    "operationId": "addItem",
                    "summary": "Add item",
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            },
                        }
                    ],
                    "responses": {
                        "201": {
                            "description": "Created",
                            "schema": {"type": "object"},
                        }
                    },
                },
            }
        },
    }
    spec_path = workspace / "swagger.json"
    spec_path.write_text(json.dumps(spec))
    return "swagger.json"


@pytest.mark.asyncio
async def test_openapi3_parse_endpoints(workspace: Path) -> None:
    path = _write_openapi3_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    assert len(endpoints) == 2
    methods = {e["method"] for e in endpoints}
    assert methods == {"GET", "POST"}


@pytest.mark.asyncio
async def test_openapi3_parse_params(workspace: Path) -> None:
    path = _write_openapi3_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    get_ep = next(e for e in endpoints if e["method"] == "GET")
    assert len(get_ep["params"]) == 1
    assert get_ep["params"][0]["name"] == "limit"
    assert get_ep["params"][0]["in"] == "query"


@pytest.mark.asyncio
async def test_openapi3_parse_request_body(workspace: Path) -> None:
    path = _write_openapi3_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    post_ep = next(e for e in endpoints if e["method"] == "POST")
    assert post_ep["request_body"] != {}
    assert "properties" in post_ep["request_body"]


@pytest.mark.asyncio
async def test_openapi3_parse_response_schema(workspace: Path) -> None:
    path = _write_openapi3_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    get_ep = next(e for e in endpoints if e["method"] == "GET")
    assert get_ep["response_schema"]["type"] == "array"


@pytest.mark.asyncio
async def test_openapi3_parse_security(workspace: Path) -> None:
    path = _write_openapi3_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    post_ep = next(e for e in endpoints if e["method"] == "POST")
    assert len(post_ep["security"]) > 0


@pytest.mark.asyncio
async def test_swagger2_parse_endpoints(workspace: Path) -> None:
    path = _write_swagger2_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    assert len(endpoints) == 2
    methods = {e["method"] for e in endpoints}
    assert methods == {"GET", "POST"}


@pytest.mark.asyncio
async def test_swagger2_parse_body_schema(workspace: Path) -> None:
    path = _write_swagger2_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    post_ep = next(e for e in endpoints if e["method"] == "POST")
    assert post_ep["request_body"] != {}


@pytest.mark.asyncio
async def test_swagger2_parse_response_schema(workspace: Path) -> None:
    path = _write_swagger2_spec(workspace)
    endpoints = await openapi_parse(path, str(workspace))

    get_ep = next(e for e in endpoints if e["method"] == "GET")
    assert get_ep["response_schema"]["type"] == "array"


@pytest.mark.asyncio
async def test_parse_file_not_found(workspace: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await openapi_parse("missing.yaml", str(workspace))


@pytest.mark.asyncio
async def test_parse_invalid_format(workspace: Path) -> None:
    (workspace / "bad.json").write_text(json.dumps({"foo": "bar"}))
    with pytest.raises(ValueError, match="Cannot detect"):
        await openapi_parse("bad.json", str(workspace))


@pytest.mark.asyncio
async def test_parse_flask_demo_spec() -> None:
    """Integration: parse the actual flask-todo-api OpenAPI spec."""
    demo_path = Path(__file__).parent.parent.parent / "demo" / "flask-todo-api"
    if not (demo_path / "docs" / "openapi.yaml").exists():
        pytest.skip("Demo spec not found")

    endpoints = await openapi_parse("docs/openapi.yaml", str(demo_path))

    # The spec defines: GET /api/todos, POST /api/todos,
    # GET /api/todos/{todoId}, PUT /api/todos/{todoId},
    # DELETE /api/todos/{todoId}, GET /api/health
    assert len(endpoints) == 6

    paths = {e["path"] for e in endpoints}
    assert "/api/todos" in paths
    assert "/api/todos/{todoId}" in paths
    assert "/api/health" in paths

    methods = {(e["method"], e["path"]) for e in endpoints}
    assert ("GET", "/api/todos") in methods
    assert ("POST", "/api/todos") in methods
    assert ("GET", "/api/todos/{todoId}") in methods
    assert ("PUT", "/api/todos/{todoId}") in methods
    assert ("DELETE", "/api/todos/{todoId}") in methods
    assert ("GET", "/api/health") in methods
