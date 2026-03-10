"""Tests for git operation tools."""

import subprocess
import pytest
from pathlib import Path

from guardian.tools.git_ops import git_status, git_diff, git_branch, git_commit


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )
    # Create initial commit
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_path), capture_output=True, check=True,
    )
    return tmp_path


@pytest.mark.asyncio
async def test_git_status_clean(git_repo: Path) -> None:
    status = await git_status(str(git_repo))
    assert status == ""


@pytest.mark.asyncio
async def test_git_status_modified(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("# Updated\n")
    status = await git_status(str(git_repo))
    assert "M" in status
    assert "README.md" in status


@pytest.mark.asyncio
async def test_git_status_untracked(git_repo: Path) -> None:
    (git_repo / "new_file.txt").write_text("hello\n")
    status = await git_status(str(git_repo))
    assert "??" in status
    assert "new_file.txt" in status


@pytest.mark.asyncio
async def test_git_diff_shows_changes(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("# Updated\n")
    diff = await git_diff(repo_path=str(git_repo))
    assert "+# Updated" in diff
    assert "-# Test" in diff


@pytest.mark.asyncio
async def test_git_diff_specific_file(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("# Updated\n")
    (git_repo / "other.txt").write_text("other\n")
    diff = await git_diff("README.md", str(git_repo))
    assert "README.md" in diff
    assert "other" not in diff


@pytest.mark.asyncio
async def test_git_branch_creates(git_repo: Path) -> None:
    result = await git_branch("feature-test", str(git_repo))
    assert "feature-test" in result
    # Verify we're on the new branch
    proc = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(git_repo), capture_output=True, text=True,
    )
    assert proc.stdout.strip() == "feature-test"


@pytest.mark.asyncio
async def test_git_commit_stages_and_commits(git_repo: Path) -> None:
    (git_repo / "new.txt").write_text("content\n")
    result = await git_commit("add new file", str(git_repo))
    assert "Committed:" in result
    assert "add new file" in result

    # Verify the commit exists
    proc = subprocess.run(
        ["git", "log", "--oneline", "-1"],
        cwd=str(git_repo), capture_output=True, text=True,
    )
    assert "add new file" in proc.stdout
