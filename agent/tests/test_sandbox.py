"""Tests for Docker sandbox runner and result parser."""

import pytest
from pathlib import Path

import subprocess

from guardian.sandbox.runner import (
    SandboxConfig,
    SandboxResult,
    detect_test_runner,
    run_in_sandbox,
    run_pytest,
    PYTHON_IMAGE,
    NODE_IMAGE,
    _docker_available,
)
from guardian.sandbox.result_parser import (
    TestCase,
    TestSuiteResult,
    parse_pytest_output,
    parse_jest_output,
    parse_test_output,
)


# === SandboxConfig tests ===

def test_sandbox_config_defaults() -> None:
    config = SandboxConfig()
    assert config.image == PYTHON_IMAGE
    assert config.timeout == 120
    assert config.memory == "512m"
    assert config.cpus == "1"
    assert config.network == "none"
    assert config.readonly_mount is False


def test_sandbox_config_custom() -> None:
    config = SandboxConfig(
        image="custom-image",
        command=["python", "-m", "pytest"],
        timeout=60,
        memory="1g",
        network="bridge",
    )
    assert config.image == "custom-image"
    assert config.timeout == 60
    assert config.memory == "1g"
    assert config.network == "bridge"


# === SandboxResult tests ===

def test_sandbox_result_fields() -> None:
    result = SandboxResult(
        exit_code=0,
        stdout="all passed",
        stderr="",
        timed_out=False,
        command="pytest -v",
        image=PYTHON_IMAGE,
        duration_ms=1500,
    )
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.duration_ms == 1500


# === detect_test_runner tests ===

def test_detect_pytest(tmp_path: Path) -> None:
    (tmp_path / "test_foo.py").write_text("def test_bar(): pass\n")
    assert detect_test_runner(str(tmp_path)) == "pytest"


def test_detect_jest(tmp_path: Path) -> None:
    (tmp_path / "app.test.js").write_text("test('works', () => {})\n")
    assert detect_test_runner(str(tmp_path)) == "jest"


def test_detect_both_prefers_pytest(tmp_path: Path) -> None:
    (tmp_path / "test_foo.py").write_text("def test_bar(): pass\n")
    (tmp_path / "app.test.js").write_text("test('works', () => {})\n")
    assert detect_test_runner(str(tmp_path)) == "pytest"


def test_detect_unknown(tmp_path: Path) -> None:
    (tmp_path / "readme.md").write_text("# Hello\n")
    assert detect_test_runner(str(tmp_path)) == "unknown"


# === run_in_sandbox tests (non-Docker) ===

@pytest.mark.asyncio
async def test_run_in_sandbox_missing_repo() -> None:
    result = await run_in_sandbox("/nonexistent/path/xyz")
    assert result.exit_code == 1
    assert "not available" in result.stderr or "does not exist" in result.stderr


# === parse_pytest_output tests ===

PYTEST_ALL_PASS = """\
============================= test session starts =============================
platform linux -- Python 3.11.9, pytest-8.4.2
collected 3 items

tests/test_api.py::test_health PASSED                                    [ 33%]
tests/test_api.py::test_list_todos PASSED                                [ 66%]
tests/test_api.py::test_create_todo PASSED                               [100%]

============================== 3 passed in 0.05s ==============================
"""

PYTEST_WITH_FAILURES = """\
============================= test session starts =============================
collected 5 items

tests/test_api.py::test_health PASSED                                    [ 20%]
tests/test_api.py::test_list_todos PASSED                                [ 40%]
tests/test_api.py::test_create_todo FAILED                               [ 60%]
tests/test_api.py::test_update_todo PASSED                               [ 80%]
tests/test_api.py::test_delete_todo FAILED                               [100%]

=================================== FAILURES ===================================
__________________ test_create_todo __________________

    assert response.status_code == 201
AssertionError: assert 400 == 201

__________________ test_delete_todo __________________

    assert response.status_code == 200
AssertionError: assert 404 == 200

=========================== 2 failed, 3 passed in 0.08s ===========================
"""

PYTEST_WITH_SKIPS = """\
============================= test session starts =============================
collected 4 items

tests/test_api.py::test_one PASSED
tests/test_api.py::test_two SKIPPED
tests/test_api.py::test_three PASSED
tests/test_api.py::test_four SKIPPED

========================= 2 passed, 2 skipped in 0.03s =========================
"""


def test_parse_pytest_all_pass() -> None:
    result = parse_pytest_output(PYTEST_ALL_PASS)
    assert result.runner == "pytest"
    assert result.passed == 3
    assert result.failed == 0
    assert result.total == 3
    assert result.all_passed is True
    assert len(result.test_cases) == 3
    assert result.duration_s == 0.05


def test_parse_pytest_with_failures() -> None:
    result = parse_pytest_output(PYTEST_WITH_FAILURES)
    assert result.passed == 3
    assert result.failed == 2
    assert result.total == 5
    assert result.all_passed is False

    failed_tests = [tc for tc in result.test_cases if tc.status == "failed"]
    assert len(failed_tests) == 2
    names = {tc.name for tc in failed_tests}
    assert "test_create_todo" in names
    assert "test_delete_todo" in names


def test_parse_pytest_with_skips() -> None:
    result = parse_pytest_output(PYTEST_WITH_SKIPS)
    assert result.passed == 2
    assert result.skipped == 2
    assert result.total == 4
    assert result.all_passed is True  # skips are OK


def test_parse_pytest_test_case_details() -> None:
    result = parse_pytest_output(PYTEST_ALL_PASS)
    tc = result.test_cases[0]
    assert tc.name == "test_health"
    assert tc.status == "passed"
    assert tc.file == "tests/test_api.py"


def test_parse_pytest_empty() -> None:
    result = parse_pytest_output("")
    assert result.total == 0
    assert result.all_passed is False


# === parse_jest_output tests ===

JEST_ALL_PASS = """\
 PASS  src/__tests__/api.test.ts
  API Tests
    ✓ should return health status (5 ms)
    ✓ should list items (12 ms)
    ✓ should create item (8 ms)

Tests:  3 passed, 3 total
Time:   1.234 s
"""

JEST_WITH_FAILURES = """\
 FAIL  src/__tests__/api.test.ts
  API Tests
    ✓ should return health status (5 ms)
    ✕ should list items (12 ms)
    ✓ should create item (8 ms)
    ✕ should delete item (3 ms)

Tests:  2 failed, 2 passed, 4 total
Time:   1.567 s
"""


def test_parse_jest_all_pass() -> None:
    result = parse_jest_output(JEST_ALL_PASS)
    assert result.runner == "jest"
    assert result.passed == 3
    assert result.failed == 0
    assert result.total == 3
    assert result.all_passed is True
    assert result.duration_s == 1.234


def test_parse_jest_with_failures() -> None:
    result = parse_jest_output(JEST_WITH_FAILURES)
    assert result.passed == 2
    assert result.failed == 2
    assert result.total == 4
    assert result.all_passed is False

    failed_tests = [tc for tc in result.test_cases if tc.status == "failed"]
    assert len(failed_tests) == 2


def test_parse_jest_empty() -> None:
    result = parse_jest_output("")
    assert result.total == 0
    assert result.all_passed is False


# === parse_test_output dispatch tests ===

def test_parse_test_output_pytest() -> None:
    result = parse_test_output(PYTEST_ALL_PASS, "pytest")
    assert result.runner == "pytest"
    assert result.all_passed is True


def test_parse_test_output_jest() -> None:
    result = parse_test_output(JEST_ALL_PASS, "jest")
    assert result.runner == "jest"
    assert result.all_passed is True


# === TestSuiteResult properties ===

def test_success_rate() -> None:
    result = TestSuiteResult(runner="pytest", passed=8, failed=2, total=10)
    assert result.success_rate == 0.8


def test_success_rate_zero_total() -> None:
    result = TestSuiteResult(runner="pytest")
    assert result.success_rate == 0.0


# === Integration: run_in_sandbox with Docker (conditional) ===

@pytest.mark.asyncio
async def test_run_pytest_in_sandbox(tmp_path: Path) -> None:
    """Integration test: actually run pytest in Docker container.

    This test is skipped if Docker is not available.
    """
    if not _docker_available():
        pytest.skip("Docker is not available")

    # Also check if Docker daemon is actually running
    try:
        proc = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=5,
        )
        if proc.returncode != 0:
            pytest.skip("Docker daemon is not running")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("Docker daemon is not reachable")

    # Create a simple test file
    (tmp_path / "test_example.py").write_text(
        "def test_addition():\n"
        "    assert 1 + 1 == 2\n"
        "\n"
        "def test_string():\n"
        "    assert 'hello'.upper() == 'HELLO'\n"
    )

    result = await run_pytest(str(tmp_path), test_files=["test_example.py"])

    # Parse the output
    parsed = parse_pytest_output(result.stdout)

    assert result.exit_code == 0, f"pytest failed: {result.stderr}"
    assert parsed.passed == 2
    assert parsed.all_passed is True
