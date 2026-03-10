"""Evaluation harness — run test-guardian against demo repos and measure quality.

Metrics:
  - Endpoint detection rate (target: 80%+)
  - Test generation coverage
  - Test pass rate (target: 80%+)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardian.tools.code_intel import detect_framework, extract_endpoints
from guardian.tools.spec_parser import openapi_parse

logger = logging.getLogger(__name__)


@dataclass
class DemoRepo:
    """A demo repository to evaluate against."""

    name: str
    path: str  # Relative to project root, or absolute path
    framework: str
    expected_endpoints: int
    spec_path: str | None = None  # Path to OpenAPI spec relative to repo
    absolute: bool = False  # If True, path is an absolute path


@dataclass
class EvalResult:
    """Result of evaluating against a single demo repo."""

    repo_name: str
    framework_detected: str
    framework_correct: bool
    endpoints_expected: int
    endpoints_detected: int
    endpoint_detection_rate: float
    spec_endpoints: int = 0
    spec_match_rate: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalSummary:
    """Summary across all evaluated repos."""

    total_repos: int
    repos_passed: int
    avg_detection_rate: float
    framework_accuracy: float
    results: list[EvalResult] = field(default_factory=list)


# Known demo repos (relative to project root, or absolute)
DEMO_REPOS = [
    DemoRepo(
        name="flask-todo-api",
        path="demo/flask-todo-api",
        framework="flask",
        expected_endpoints=6,
        spec_path="docs/openapi.yaml",
    ),
    DemoRepo(
        name="fastapi-notes",
        path="demo/fastapi-notes",
        framework="fastapi",
        expected_endpoints=6,
    ),
    DemoRepo(
        name="express-users-api",
        path="demo/express-users-api",
        framework="express",
        expected_endpoints=6,
    ),
]

# External real-world project for cross-project evaluation
EXTERNAL_REPOS = [
    DemoRepo(
        name="checkpoint-runtime",
        path=r"C:\Users\jasim\Documents\Islamic\checkpoint",
        framework="fastapi",
        expected_endpoints=33,
        absolute=True,
    ),
]


async def evaluate_repo(
    demo: DemoRepo,
    project_root: str | Path,
) -> EvalResult:
    """Evaluate test-guardian's code intelligence against a single demo repo."""
    root = Path(project_root)
    repo_path = demo.path if demo.absolute else str(root / demo.path)

    # 1. Framework detection
    detected_framework = await detect_framework(repo_path)
    framework_correct = detected_framework == demo.framework

    # 2. Endpoint extraction from source code
    endpoints = await extract_endpoints(repo_path, detected_framework)
    detection_rate = len(endpoints) / demo.expected_endpoints if demo.expected_endpoints > 0 else 0.0

    # 3. Spec parsing (if available)
    spec_endpoints = 0
    spec_match_rate = 0.0
    if demo.spec_path:
        spec_base = Path(repo_path)
        spec_file = spec_base / demo.spec_path
        if spec_file.exists():
            try:
                spec_eps = await openapi_parse(demo.spec_path, repo_path)
                spec_endpoints = len(spec_eps)
                spec_match_rate = spec_endpoints / demo.expected_endpoints if demo.expected_endpoints > 0 else 0.0
            except Exception as e:
                logger.warning("Spec parsing failed for %s: %s", demo.name, e)

    result = EvalResult(
        repo_name=demo.name,
        framework_detected=detected_framework,
        framework_correct=framework_correct,
        endpoints_expected=demo.expected_endpoints,
        endpoints_detected=len(endpoints),
        endpoint_detection_rate=detection_rate,
        spec_endpoints=spec_endpoints,
        spec_match_rate=spec_match_rate,
        details={
            "endpoints": [
                {"method": e["method"], "path": e["path"]}
                for e in endpoints
            ],
        },
    )

    logger.info(
        "Eval %s: framework=%s (correct=%s), endpoints=%d/%d (%.0f%%)",
        demo.name,
        detected_framework,
        framework_correct,
        len(endpoints),
        demo.expected_endpoints,
        detection_rate * 100,
    )

    return result


async def evaluate_all(
    project_root: str | Path,
    demos: list[DemoRepo] | None = None,
) -> EvalSummary:
    """Evaluate test-guardian against all demo repos.

    Args:
        project_root: Root of the test-guardian project.
        demos: Override the default demo repos.

    Returns:
        EvalSummary with overall metrics.
    """
    if demos is None:
        demos = DEMO_REPOS

    results: list[EvalResult] = []
    for demo in demos:
        if demo.absolute:
            repo_dir = Path(demo.path)
        else:
            repo_dir = Path(project_root) / demo.path
        if not repo_dir.exists():
            logger.warning("Demo repo not found: %s", demo.path)
            continue

        result = await evaluate_repo(demo, project_root)
        results.append(result)

    if not results:
        return EvalSummary(
            total_repos=0,
            repos_passed=0,
            avg_detection_rate=0.0,
            framework_accuracy=0.0,
        )

    # Compute summary
    total = len(results)
    passed = sum(1 for r in results if r.endpoint_detection_rate >= 0.8)
    avg_rate = sum(r.endpoint_detection_rate for r in results) / total
    fw_accuracy = sum(1 for r in results if r.framework_correct) / total

    summary = EvalSummary(
        total_repos=total,
        repos_passed=passed,
        avg_detection_rate=avg_rate,
        framework_accuracy=fw_accuracy,
        results=results,
    )

    logger.info(
        "Eval summary: %d/%d repos passed (%.0f%% avg detection, %.0f%% fw accuracy)",
        passed,
        total,
        avg_rate * 100,
        fw_accuracy * 100,
    )

    return summary


async def evaluate_full(
    project_root: str | Path,
) -> EvalSummary:
    """Evaluate against all demo repos AND external real-world projects."""
    all_repos = DEMO_REPOS + EXTERNAL_REPOS
    return await evaluate_all(project_root, demos=all_repos)


def format_report(summary: EvalSummary) -> str:
    """Format an evaluation summary as a readable report."""
    lines = [
        "=" * 60,
        "test-guardian Evaluation Report",
        "=" * 60,
        "",
        f"Repos evaluated:      {summary.total_repos}",
        f"Repos passing (>=80%): {summary.repos_passed}/{summary.total_repos}",
        f"Avg detection rate:   {summary.avg_detection_rate:.0%}",
        f"Framework accuracy:   {summary.framework_accuracy:.0%}",
        "",
        "-" * 60,
    ]

    for result in summary.results:
        status = "PASS" if result.endpoint_detection_rate >= 0.8 else "FAIL"
        lines.extend([
            f"",
            f"[{status}] {result.repo_name}",
            f"  Framework:   {result.framework_detected} "
            f"({'correct' if result.framework_correct else 'WRONG'})",
            f"  Endpoints:   {result.endpoints_detected}/{result.endpoints_expected} "
            f"({result.endpoint_detection_rate:.0%})",
        ])
        if result.spec_endpoints > 0:
            lines.append(
                f"  Spec parse:  {result.spec_endpoints} endpoints "
                f"({result.spec_match_rate:.0%})"
            )
        if result.details.get("endpoints"):
            lines.append("  Detected:")
            for ep in result.details["endpoints"]:
                lines.append(f"    {ep['method']:6s} {ep['path']}")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)
