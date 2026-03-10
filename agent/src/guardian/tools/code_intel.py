"""Code intelligence — AST-based endpoint detection and framework identification.

Uses regex-based parsing (tree-sitter can be added later as an enhancement).
Detects Flask, FastAPI, and Express route decorators/patterns.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Framework detection patterns
FRAMEWORK_PATTERNS = {
    "flask": [
        r"from\s+flask\s+import",
        r"import\s+flask",
        r"Flask\(__name__\)",
        r"@app\.route\(",
    ],
    "fastapi": [
        r"from\s+fastapi\s+import",
        r"import\s+fastapi",
        r"FastAPI\(",
        r"@(?:app|router)\.(get|post|put|patch|delete)\(",
    ],
    "express": [
        r"require\(['\"]express['\"]\)",
        r"import\s+express\s+from",
        r"express\(\)",
        r"(?:app|router)\.(get|post|put|patch|delete)\(",
    ],
}

# Route patterns per framework
ROUTE_PATTERNS = {
    "flask": re.compile(
        r"""@(?:\w+)\.route\(\s*['"]([^'"]+)['"]\s*(?:,\s*methods\s*=\s*\[([^\]]+)\])?\s*\)"""
        r"""\s*\ndef\s+(\w+)""",
        re.MULTILINE,
    ),
    "flask_method": re.compile(
        r"""@(?:\w+)\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]""",
        re.MULTILINE,
    ),
    "fastapi": re.compile(
        r"""@(?:\w+)\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]\s*""",
        re.MULTILINE,
    ),
    "express": re.compile(
        r"""(?:app|router)\.(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]""",
        re.MULTILINE,
    ),
}


async def detect_framework(repo_path: str = ".") -> str:
    """Detect the API framework used in the repository."""
    root = Path(repo_path)
    scores: dict[str, int] = {"flask": 0, "fastapi": 0, "express": 0}

    # Check Python files
    for pyfile in root.rglob("*.py"):
        if _should_skip(pyfile):
            continue
        try:
            content = pyfile.read_text(encoding="utf-8", errors="replace")
            for framework, patterns in FRAMEWORK_PATTERNS.items():
                if framework == "express":
                    continue
                for pattern in patterns:
                    if re.search(pattern, content):
                        scores[framework] += 1
        except OSError:
            continue

    # Check JS/TS files
    for ext in ("*.js", "*.ts", "*.mjs"):
        for jsfile in root.rglob(ext):
            if _should_skip(jsfile):
                continue
            try:
                content = jsfile.read_text(encoding="utf-8", errors="replace")
                for pattern in FRAMEWORK_PATTERNS["express"]:
                    if re.search(pattern, content):
                        scores["express"] += 1
            except OSError:
                continue

    # Return the framework with highest score
    if max(scores.values()) == 0:
        return "unknown"
    return max(scores, key=lambda k: scores[k])


async def extract_endpoints(
    repo_path: str = ".", framework: str | None = None
) -> list[dict[str, Any]]:
    """Extract API endpoints from source code using regex-based AST analysis."""
    root = Path(repo_path)

    if not framework:
        framework = await detect_framework(repo_path)

    endpoints: list[dict[str, Any]] = []

    if framework in ("flask", "fastapi"):
        for pyfile in root.rglob("*.py"):
            if _should_skip(pyfile):
                continue
            try:
                content = pyfile.read_text(encoding="utf-8", errors="replace")
                eps = _extract_python_routes(content, framework, pyfile, root)
                endpoints.extend(eps)
            except OSError:
                continue

    elif framework == "express":
        for ext in ("*.js", "*.ts", "*.mjs"):
            for jsfile in root.rglob(ext):
                if _should_skip(jsfile):
                    continue
                try:
                    content = jsfile.read_text(encoding="utf-8", errors="replace")
                    eps = _extract_express_routes(content, jsfile, root)
                    endpoints.extend(eps)
                except OSError:
                    continue

    return endpoints


async def extract_symbols(
    path: str,
    query: str = "functions",
    repo_path: str = ".",
) -> list[dict[str, Any]]:
    """Extract code symbols (functions, classes, imports) from a file."""
    full_path = Path(repo_path) / path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    content = full_path.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")

    if query == "functions":
        return _extract_functions(lines, path)
    elif query == "classes":
        return _extract_classes(lines, path)
    elif query == "imports":
        return _extract_imports(lines, path)
    elif query == "routes":
        framework = await detect_framework(repo_path)
        return await extract_endpoints(repo_path, framework)
    else:
        raise ValueError(f"Unknown query type: {query}")


def _extract_python_routes(
    content: str, framework: str, file_path: Path, root: Path
) -> list[dict[str, Any]]:
    """Extract route definitions from Python files."""
    endpoints: list[dict[str, Any]] = []
    lines = content.split("\n")
    relative_path = str(file_path.relative_to(root))

    if framework == "flask":
        # Match @app.route('/path', methods=['GET', 'POST'])
        for match in ROUTE_PATTERNS["flask"].finditer(content):
            path = match.group(1)
            methods_str = match.group(2)
            handler = match.group(3)
            line_no = content[: match.start()].count("\n") + 1

            if methods_str:
                methods = [
                    m.strip().strip("'\"")
                    for m in methods_str.split(",")
                ]
            else:
                methods = ["GET"]

            for method in methods:
                endpoints.append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "handler": handler,
                        "file": relative_path,
                        "line": line_no,
                    }
                )

    # Also check for Flask method-style decorators and FastAPI
    pattern_key = "flask_method" if framework == "flask" else "fastapi"
    for match in ROUTE_PATTERNS[pattern_key].finditer(content):
        method = match.group(1).upper()
        path = match.group(2)
        line_no = content[: match.start()].count("\n") + 1

        # Find the handler function name (next def after the decorator)
        handler = "unknown"
        for i, line in enumerate(lines[line_no:], line_no + 1):
            func_match = re.match(r"\s*(?:async\s+)?def\s+(\w+)", line)
            if func_match:
                handler = func_match.group(1)
                break

        endpoints.append(
            {
                "method": method,
                "path": path,
                "handler": handler,
                "file": relative_path,
                "line": line_no,
            }
        )

    return endpoints


def _extract_express_routes(
    content: str, file_path: Path, root: Path
) -> list[dict[str, Any]]:
    """Extract route definitions from Express files."""
    endpoints: list[dict[str, Any]] = []
    relative_path = str(file_path.relative_to(root))

    for match in ROUTE_PATTERNS["express"].finditer(content):
        method = match.group(1).upper()
        path = match.group(2)
        line_no = content[: match.start()].count("\n") + 1

        endpoints.append(
            {
                "method": method,
                "path": path,
                "handler": f"anonymous_{line_no}",
                "file": relative_path,
                "line": line_no,
            }
        )

    return endpoints


def _extract_functions(
    lines: list[str], file_path: str
) -> list[dict[str, Any]]:
    """Extract function definitions."""
    results: list[dict[str, Any]] = []
    for i, line in enumerate(lines, 1):
        match = re.match(r"\s*(?:async\s+)?def\s+(\w+)\s*\(", line)
        if match:
            results.append(
                {"name": match.group(1), "file": file_path, "line": i, "type": "function"}
            )
        # JS/TS function
        match = re.match(r"\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)", line)
        if match:
            results.append(
                {"name": match.group(1), "file": file_path, "line": i, "type": "function"}
            )
    return results


def _extract_classes(
    lines: list[str], file_path: str
) -> list[dict[str, Any]]:
    """Extract class definitions."""
    results: list[dict[str, Any]] = []
    for i, line in enumerate(lines, 1):
        match = re.match(r"\s*class\s+(\w+)", line)
        if match:
            results.append(
                {"name": match.group(1), "file": file_path, "line": i, "type": "class"}
            )
    return results


def _extract_imports(
    lines: list[str], file_path: str
) -> list[dict[str, Any]]:
    """Extract import statements."""
    results: list[dict[str, Any]] = []
    for i, line in enumerate(lines, 1):
        if re.match(r"\s*(import|from)\s+", line):
            results.append(
                {"statement": line.strip(), "file": file_path, "line": i, "type": "import"}
            )
        elif re.match(r"\s*(const|let|var|import)\s+.*require\(|import\s+", line):
            results.append(
                {"statement": line.strip(), "file": file_path, "line": i, "type": "import"}
            )
    return results


def _should_skip(path: Path) -> bool:
    """Check if a file should be skipped during analysis."""
    skip_dirs = {
        ".git", "node_modules", "__pycache__", "venv", ".venv",
        "dist", ".test-guardian", ".pytest_cache",
    }
    return any(part in skip_dirs for part in path.parts)
