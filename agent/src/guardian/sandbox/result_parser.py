"""Parse test results from pytest and jest output into structured data."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestCase:
    """A single test case result."""

    name: str
    status: str  # "passed", "failed", "skipped", "error"
    file: str = ""
    duration_ms: float = 0.0
    error_message: str = ""


@dataclass
class TestSuiteResult:
    """Structured result from parsing test output."""

    runner: str  # "pytest" or "jest"
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_s: float = 0.0
    test_cases: list[TestCase] = field(default_factory=list)
    all_passed: bool = False
    raw_summary: str = ""

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


def parse_pytest_output(output: str) -> TestSuiteResult:
    """Parse pytest verbose output into structured results.

    Handles:
      - test_foo.py::test_name PASSED
      - test_foo.py::test_name FAILED
      - Summary line: "== X passed, Y failed in Z.ZZs =="
    """
    result = TestSuiteResult(runner="pytest")

    # Parse individual test results
    # Pattern: tests/test_foo.py::test_bar PASSED/FAILED/SKIPPED
    test_pattern = re.compile(
        r"^([\w/\\.-]+)::(\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)",
        re.MULTILINE,
    )
    for match in test_pattern.finditer(output):
        file_path = match.group(1)
        test_name = match.group(2)
        status = match.group(3).lower()

        tc = TestCase(
            name=test_name,
            status=status,
            file=file_path,
        )

        if status == "failed" or status == "error":
            # Try to extract the failure message
            tc.error_message = _extract_pytest_failure(output, test_name)

        result.test_cases.append(tc)

    # Parse summary line
    # Pattern: "= 5 passed in 0.03s =" or "= 3 passed, 2 failed in 0.05s ="
    summary_pattern = re.compile(
        r"=+\s*(.*?)\s+in\s+([\d.]+)s?\s*=+",
        re.MULTILINE,
    )
    summary_match = summary_pattern.search(output)
    if summary_match:
        result.raw_summary = summary_match.group(0)
        summary_text = summary_match.group(1)
        result.duration_s = float(summary_match.group(2))

        # Extract counts from summary
        passed_match = re.search(r"(\d+)\s+passed", summary_text)
        failed_match = re.search(r"(\d+)\s+failed", summary_text)
        skipped_match = re.search(r"(\d+)\s+(?:skipped|deselected)", summary_text)
        error_match = re.search(r"(\d+)\s+error", summary_text)

        if passed_match:
            result.passed = int(passed_match.group(1))
        if failed_match:
            result.failed = int(failed_match.group(1))
        if skipped_match:
            result.skipped = int(skipped_match.group(1))
        if error_match:
            result.errors = int(error_match.group(1))

    result.total = result.passed + result.failed + result.skipped + result.errors
    result.all_passed = result.failed == 0 and result.errors == 0 and result.passed > 0

    return result


def parse_jest_output(output: str) -> TestSuiteResult:
    """Parse jest verbose output into structured results.

    Handles:
      - ✓ test name (Xms)
      - ✕ test name (Xms)
      - Summary: Tests: X passed, Y failed, Z total
    """
    result = TestSuiteResult(runner="jest")

    # Parse individual test results
    # Pattern: ✓ test name (123 ms)  or  ✕ test name (45 ms)
    # Also handle PASS/FAIL prefix lines
    pass_pattern = re.compile(
        r"[✓✔]\s+(.+?)(?:\s+\((\d+)\s*m?s\))?$",
        re.MULTILINE,
    )
    fail_pattern = re.compile(
        r"[✕✗×]\s+(.+?)(?:\s+\((\d+)\s*m?s\))?$",
        re.MULTILINE,
    )

    for match in pass_pattern.finditer(output):
        tc = TestCase(
            name=match.group(1).strip(),
            status="passed",
            duration_ms=float(match.group(2) or 0),
        )
        result.test_cases.append(tc)

    for match in fail_pattern.finditer(output):
        tc = TestCase(
            name=match.group(1).strip(),
            status="failed",
            duration_ms=float(match.group(2) or 0),
        )
        result.test_cases.append(tc)

    # Parse summary
    # Pattern: "Tests:  X passed, Y failed, Z total"
    tests_summary = re.search(
        r"Tests:\s+(.*?)(\d+)\s+total",
        output,
    )
    if tests_summary:
        summary_text = tests_summary.group(0)
        result.raw_summary = summary_text

        passed_match = re.search(r"(\d+)\s+passed", summary_text)
        failed_match = re.search(r"(\d+)\s+failed", summary_text)
        skipped_match = re.search(r"(\d+)\s+skipped", summary_text)

        if passed_match:
            result.passed = int(passed_match.group(1))
        if failed_match:
            result.failed = int(failed_match.group(1))
        if skipped_match:
            result.skipped = int(skipped_match.group(1))

        result.total = int(tests_summary.group(2))

    # Parse time
    time_match = re.search(r"Time:\s+([\d.]+)\s*s", output)
    if time_match:
        result.duration_s = float(time_match.group(1))

    if result.total == 0:
        result.total = len(result.test_cases)
        result.passed = sum(1 for tc in result.test_cases if tc.status == "passed")
        result.failed = sum(1 for tc in result.test_cases if tc.status == "failed")

    result.all_passed = result.failed == 0 and result.errors == 0 and result.passed > 0

    return result


def parse_test_output(output: str, runner: str = "pytest") -> TestSuiteResult:
    """Parse test output using the appropriate parser.

    Args:
        output: Raw test output string.
        runner: Test runner type ("pytest" or "jest").

    Returns:
        Structured TestSuiteResult.
    """
    if runner == "jest":
        return parse_jest_output(output)
    return parse_pytest_output(output)


def _extract_pytest_failure(output: str, test_name: str) -> str:
    """Extract failure details for a specific pytest test."""
    # Look for FAILURES section
    pattern = re.compile(
        rf"_{2,}\s+{re.escape(test_name)}\s+_{2,}\n(.*?)(?=\n_{2,}|\n={2,})",
        re.DOTALL,
    )
    match = pattern.search(output)
    if match:
        return match.group(1).strip()[:500]
    return ""
