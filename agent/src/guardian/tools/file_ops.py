"""File operation tools: read, write (via diff), search, tree."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


async def file_read(path: str, repo_path: str = ".") -> str:
    """Read file contents with line numbers."""
    full_path = Path(repo_path) / path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not full_path.is_file():
        raise ValueError(f"Not a file: {path}")

    content = full_path.read_text(encoding="utf-8", errors="replace")
    lines = content.split("\n")
    numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered)


async def file_write(path: str, content: str, repo_path: str = ".") -> str:
    """Write content to a file. Creates parent directories if needed.

    In production, this would apply a unified diff. For now, it writes directly
    but the checkpoint system ensures safety.
    """
    full_path = Path(repo_path) / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return f"Written: {path} ({len(content)} bytes)"


async def file_search(
    pattern: str, path: str = ".", repo_path: str = "."
) -> list[dict[str, Any]]:
    """Search for a pattern in files using ripgrep or fallback to Python."""
    search_path = Path(repo_path) / path
    if not search_path.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    results: list[dict[str, Any]] = []

    # Try ripgrep first
    try:
        proc = subprocess.run(
            ["rg", "--json", "--max-count", "50", pattern, str(search_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            import json

            for line in proc.stdout.strip().split("\n"):
                if not line:
                    continue
                data = json.loads(line)
                if data.get("type") == "match":
                    match_data = data["data"]
                    results.append(
                        {
                            "file": match_data["path"]["text"],
                            "line": match_data["line_number"],
                            "match": match_data["lines"]["text"].strip(),
                        }
                    )
            return results
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: Python-based search
    import re

    regex = re.compile(pattern)
    for root, _dirs, files in os.walk(search_path):
        # Skip hidden dirs and common non-code dirs
        if any(
            part.startswith(".") or part in ("node_modules", "__pycache__", "venv")
            for part in Path(root).parts
        ):
            continue
        for fname in files:
            fpath = Path(root) / fname
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.split("\n"), 1):
                    if regex.search(line):
                        results.append(
                            {
                                "file": str(fpath.relative_to(search_path)),
                                "line": i,
                                "match": line.strip(),
                            }
                        )
                        if len(results) >= 50:
                            return results
            except (OSError, UnicodeDecodeError):
                continue

    return results


async def tree(path: str = ".", depth: int = 3, repo_path: str = ".") -> str:
    """Generate a directory tree listing, respecting .gitignore patterns."""
    root = Path(repo_path) / path
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    skip = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".test-guardian",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    lines: list[str] = [str(root.name) + "/"]
    _build_tree(root, "", depth, skip, lines)
    return "\n".join(lines)


def _build_tree(
    directory: Path,
    prefix: str,
    depth: int,
    skip: set[str],
    lines: list[str],
) -> None:
    """Recursively build tree lines."""
    if depth <= 0:
        return

    try:
        entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name))
    except PermissionError:
        return

    entries = [e for e in entries if e.name not in skip]
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{prefix}{connector}{entry.name}{suffix}")

        if entry.is_dir():
            extension = "    " if is_last else "│   "
            _build_tree(entry, prefix + extension, depth - 1, skip, lines)
