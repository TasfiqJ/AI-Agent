"""Git operation tools: status, diff, branch, commit."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], repo_path: str = ".") -> str:
    """Run a git command and return stdout."""
    proc = subprocess.run(
        ["git"] + args,
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0 and proc.stderr:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


async def git_status(repo_path: str = ".") -> str:
    """Get git status: modified, staged, and untracked files."""
    return _run_git(["status", "--porcelain"], repo_path)


async def git_diff(path: str | None = None, repo_path: str = ".") -> str:
    """Get unified diff of changes."""
    args = ["diff"]
    if path:
        args.append(path)
    return _run_git(args, repo_path)


async def git_branch(name: str, repo_path: str = ".") -> str:
    """Create a new git branch."""
    _run_git(["checkout", "-b", name], repo_path)
    return f"Created and switched to branch: {name}"


async def git_commit(message: str, repo_path: str = ".") -> str:
    """Stage all changes and commit."""
    _run_git(["add", "-A"], repo_path)
    _run_git(["commit", "-m", message], repo_path)
    sha = _run_git(["rev-parse", "HEAD"], repo_path)
    return f"Committed: {sha[:8]} {message}"
