"""Tests for code intelligence — framework detection and endpoint extraction."""

import pytest
from pathlib import Path

from guardian.tools.code_intel import (
    detect_framework,
    extract_endpoints,
    extract_symbols,
)


@pytest.fixture
def flask_repo(tmp_path: Path) -> Path:
    """Create a minimal Flask repo."""
    app_py = tmp_path / "app.py"
    app_py.write_text(
        'from flask import Flask, jsonify, request\n'
        '\n'
        'app = Flask(__name__)\n'
        '\n'
        '@app.route("/api/items", methods=["GET"])\n'
        'def list_items():\n'
        '    return jsonify([])\n'
        '\n'
        '@app.route("/api/items", methods=["POST"])\n'
        'def create_item():\n'
        '    return jsonify({}), 201\n'
        '\n'
        '@app.route("/api/items/<int:item_id>", methods=["GET", "PUT"])\n'
        'def get_or_update_item(item_id):\n'
        '    return jsonify({})\n'
    )
    return tmp_path


@pytest.fixture
def fastapi_repo(tmp_path: Path) -> Path:
    """Create a minimal FastAPI repo."""
    app_py = tmp_path / "main.py"
    app_py.write_text(
        'from fastapi import FastAPI\n'
        '\n'
        'app = FastAPI()\n'
        '\n'
        '@app.get("/api/users")\n'
        'async def list_users():\n'
        '    return []\n'
        '\n'
        '@app.post("/api/users")\n'
        'async def create_user():\n'
        '    return {}\n'
        '\n'
        '@app.delete("/api/users/{user_id}")\n'
        'async def delete_user(user_id: int):\n'
        '    return {"ok": True}\n'
    )
    return tmp_path


@pytest.fixture
def express_repo(tmp_path: Path) -> Path:
    """Create a minimal Express repo."""
    app_js = tmp_path / "app.js"
    app_js.write_text(
        "const express = require('express');\n"
        "const app = express();\n"
        "\n"
        "app.get('/api/posts', (req, res) => {\n"
        "  res.json([]);\n"
        "});\n"
        "\n"
        "app.post('/api/posts', (req, res) => {\n"
        "  res.json({});\n"
        "});\n"
        "\n"
        "app.delete('/api/posts/:id', (req, res) => {\n"
        "  res.json({ok: true});\n"
        "});\n"
    )
    return tmp_path


# --- detect_framework tests ---

@pytest.mark.asyncio
async def test_detect_flask(flask_repo: Path) -> None:
    result = await detect_framework(str(flask_repo))
    assert result == "flask"


@pytest.mark.asyncio
async def test_detect_fastapi(fastapi_repo: Path) -> None:
    result = await detect_framework(str(fastapi_repo))
    assert result == "fastapi"


@pytest.mark.asyncio
async def test_detect_express(express_repo: Path) -> None:
    result = await detect_framework(str(express_repo))
    assert result == "express"


@pytest.mark.asyncio
async def test_detect_unknown(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_text("just a text file\n")
    result = await detect_framework(str(tmp_path))
    assert result == "unknown"


# --- extract_endpoints tests ---

@pytest.mark.asyncio
async def test_extract_flask_endpoints(flask_repo: Path) -> None:
    endpoints = await extract_endpoints(str(flask_repo), "flask")
    paths = {(e["method"], e["path"]) for e in endpoints}

    assert ("GET", "/api/items") in paths
    assert ("POST", "/api/items") in paths
    assert ("GET", "/api/items/<int:item_id>") in paths
    assert ("PUT", "/api/items/<int:item_id>") in paths


@pytest.mark.asyncio
async def test_extract_fastapi_endpoints(fastapi_repo: Path) -> None:
    endpoints = await extract_endpoints(str(fastapi_repo), "fastapi")
    paths = {(e["method"], e["path"]) for e in endpoints}

    assert ("GET", "/api/users") in paths
    assert ("POST", "/api/users") in paths
    assert ("DELETE", "/api/users/{user_id}") in paths


@pytest.mark.asyncio
async def test_extract_express_endpoints(express_repo: Path) -> None:
    endpoints = await extract_endpoints(str(express_repo), "express")
    paths = {(e["method"], e["path"]) for e in endpoints}

    assert ("GET", "/api/posts") in paths
    assert ("POST", "/api/posts") in paths
    assert ("DELETE", "/api/posts/:id") in paths


@pytest.mark.asyncio
async def test_extract_endpoints_auto_detect(flask_repo: Path) -> None:
    """Framework should be auto-detected when not provided."""
    endpoints = await extract_endpoints(str(flask_repo))
    assert len(endpoints) > 0


@pytest.mark.asyncio
async def test_extract_endpoints_unknown_framework(tmp_path: Path) -> None:
    (tmp_path / "plain.py").write_text("x = 1\n")
    endpoints = await extract_endpoints(str(tmp_path))
    assert endpoints == []


# --- extract_symbols tests ---

@pytest.mark.asyncio
async def test_extract_functions(flask_repo: Path) -> None:
    symbols = await extract_symbols("app.py", "functions", str(flask_repo))
    names = {s["name"] for s in symbols}
    assert "list_items" in names
    assert "create_item" in names


@pytest.mark.asyncio
async def test_extract_classes(tmp_path: Path) -> None:
    (tmp_path / "models.py").write_text("class User:\n    pass\n\nclass Post:\n    pass\n")
    symbols = await extract_symbols("models.py", "classes", str(tmp_path))
    names = {s["name"] for s in symbols}
    assert names == {"User", "Post"}


@pytest.mark.asyncio
async def test_extract_imports(flask_repo: Path) -> None:
    symbols = await extract_symbols("app.py", "imports", str(flask_repo))
    assert len(symbols) >= 1
    assert any("flask" in s["statement"].lower() for s in symbols)


@pytest.mark.asyncio
async def test_extract_symbols_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await extract_symbols("missing.py", "functions", str(tmp_path))


@pytest.mark.asyncio
async def test_extract_symbols_invalid_query(flask_repo: Path) -> None:
    with pytest.raises(ValueError, match="Unknown query type"):
        await extract_symbols("app.py", "invalid_query", str(flask_repo))


# --- Integration: flask-todo-api demo ---

@pytest.mark.asyncio
async def test_detect_flask_demo() -> None:
    """Integration: detect framework in the actual flask-todo-api demo."""
    demo_path = Path(__file__).parent.parent.parent / "demo" / "flask-todo-api"
    if not demo_path.exists():
        pytest.skip("Demo not found")

    result = await detect_framework(str(demo_path))
    assert result == "flask"


@pytest.mark.asyncio
async def test_extract_flask_demo_endpoints() -> None:
    """Integration: extract all 6 endpoints from the flask-todo-api demo.

    This is the Phase 2 exit criteria: point tools at flask-todo-api → all 6 endpoints detected.
    """
    demo_path = Path(__file__).parent.parent.parent / "demo" / "flask-todo-api"
    if not demo_path.exists():
        pytest.skip("Demo not found")

    endpoints = await extract_endpoints(str(demo_path), "flask")

    # The demo has 6 endpoints:
    # GET  /api/todos
    # POST /api/todos
    # GET  /api/todos/<int:todo_id>
    # PUT  /api/todos/<int:todo_id>
    # DELETE /api/todos/<int:todo_id>
    # GET  /api/health
    pairs = {(e["method"], e["path"]) for e in endpoints}

    assert ("GET", "/api/todos") in pairs, f"Missing GET /api/todos. Found: {pairs}"
    assert ("POST", "/api/todos") in pairs, f"Missing POST /api/todos. Found: {pairs}"
    assert ("GET", "/api/todos/<int:todo_id>") in pairs, f"Missing GET /api/todos/<int:todo_id>. Found: {pairs}"
    assert ("PUT", "/api/todos/<int:todo_id>") in pairs, f"Missing PUT /api/todos/<int:todo_id>. Found: {pairs}"
    assert ("DELETE", "/api/todos/<int:todo_id>") in pairs, f"Missing DELETE /api/todos/<int:todo_id>. Found: {pairs}"
    assert ("GET", "/api/health") in pairs, f"Missing GET /api/health. Found: {pairs}"

    assert len(endpoints) >= 6
