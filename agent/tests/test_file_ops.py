"""Tests for file operation tools."""

import pytest
from pathlib import Path

from guardian.tools.file_ops import file_read, file_write, file_search, tree


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a workspace with some test files."""
    # Create a simple file
    (tmp_path / "hello.py").write_text("print('hello')\nprint('world')\n")

    # Create a nested structure
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("def main():\n    return 42\n")
    (sub / "utils.py").write_text("def helper():\n    pass\n")

    deep = sub / "models"
    deep.mkdir()
    (deep / "user.py").write_text("class User:\n    pass\n")

    return tmp_path


@pytest.mark.asyncio
async def test_file_read(workspace: Path) -> None:
    content = await file_read("hello.py", str(workspace))
    assert "   1 | print('hello')" in content
    assert "   2 | print('world')" in content


@pytest.mark.asyncio
async def test_file_read_not_found(workspace: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await file_read("nonexistent.py", str(workspace))


@pytest.mark.asyncio
async def test_file_read_directory_error(workspace: Path) -> None:
    with pytest.raises(ValueError, match="Not a file"):
        await file_read("src", str(workspace))


@pytest.mark.asyncio
async def test_file_write_new(workspace: Path) -> None:
    result = await file_write("output.txt", "hello world", str(workspace))
    assert "Written: output.txt" in result
    assert (workspace / "output.txt").read_text() == "hello world"


@pytest.mark.asyncio
async def test_file_write_creates_dirs(workspace: Path) -> None:
    result = await file_write("new/nested/file.txt", "content", str(workspace))
    assert "Written:" in result
    assert (workspace / "new" / "nested" / "file.txt").read_text() == "content"


@pytest.mark.asyncio
async def test_file_search_finds_pattern(workspace: Path) -> None:
    results = await file_search("def main", ".", str(workspace))
    assert len(results) >= 1
    matches = [r for r in results if "main" in r["match"]]
    assert len(matches) >= 1


@pytest.mark.asyncio
async def test_file_search_no_results(workspace: Path) -> None:
    results = await file_search("zzz_nonexistent_zzz", ".", str(workspace))
    assert results == []


@pytest.mark.asyncio
async def test_file_search_path_not_found(workspace: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await file_search("pattern", "nonexistent", str(workspace))


@pytest.mark.asyncio
async def test_tree_basic(workspace: Path) -> None:
    result = await tree(".", 3, str(workspace))
    assert "hello.py" in result
    assert "src/" in result
    assert "main.py" in result


@pytest.mark.asyncio
async def test_tree_depth_limited(workspace: Path) -> None:
    result = await tree(".", 1, str(workspace))
    assert "src/" in result
    # At depth 1, we should see the dir but not its contents
    assert "main.py" not in result


@pytest.mark.asyncio
async def test_tree_skip_dirs(workspace: Path) -> None:
    # Create a node_modules directory
    (workspace / "node_modules").mkdir()
    (workspace / "node_modules" / "pkg.json").write_text("{}")
    result = await tree(".", 3, str(workspace))
    assert "node_modules" not in result
