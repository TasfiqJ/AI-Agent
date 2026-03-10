"""Tests for the evaluation harness.

These tests verify the Phase 6 exit criteria:
  - 80%+ endpoints detected across all demo repos
  - Framework detection is correct for all repos
"""

import pytest
from pathlib import Path

from guardian.eval.harness import (
    DemoRepo,
    EvalResult,
    EvalSummary,
    evaluate_repo,
    evaluate_all,
    evaluate_full,
    format_report,
    DEMO_REPOS,
    EXTERNAL_REPOS,
)


PROJECT_ROOT = Path(__file__).parent.parent.parent


# === Unit tests ===

def test_demo_repos_defined() -> None:
    assert len(DEMO_REPOS) == 3
    names = {r.name for r in DEMO_REPOS}
    assert names == {"flask-todo-api", "fastapi-notes", "express-users-api"}


def test_eval_result_fields() -> None:
    result = EvalResult(
        repo_name="test",
        framework_detected="flask",
        framework_correct=True,
        endpoints_expected=6,
        endpoints_detected=5,
        endpoint_detection_rate=5 / 6,
    )
    assert result.endpoint_detection_rate == pytest.approx(0.833, rel=0.01)


def test_format_report() -> None:
    summary = EvalSummary(
        total_repos=1,
        repos_passed=1,
        avg_detection_rate=1.0,
        framework_accuracy=1.0,
        results=[
            EvalResult(
                repo_name="test-repo",
                framework_detected="flask",
                framework_correct=True,
                endpoints_expected=6,
                endpoints_detected=6,
                endpoint_detection_rate=1.0,
            )
        ],
    )
    report = format_report(summary)
    assert "test-guardian Evaluation Report" in report
    assert "[PASS]" in report
    assert "100%" in report


# === Integration: evaluate individual demo repos ===

@pytest.mark.asyncio
async def test_eval_flask_todo() -> None:
    """Evaluate against flask-todo-api demo."""
    demo = DemoRepo(
        name="flask-todo-api",
        path="demo/flask-todo-api",
        framework="flask",
        expected_endpoints=6,
        spec_path="docs/openapi.yaml",
    )

    if not (PROJECT_ROOT / demo.path).exists():
        pytest.skip("Demo not found")

    result = await evaluate_repo(demo, PROJECT_ROOT)

    assert result.framework_correct, f"Expected flask, got {result.framework_detected}"
    assert result.endpoint_detection_rate >= 0.8, (
        f"Only detected {result.endpoints_detected}/{result.endpoints_expected} "
        f"({result.endpoint_detection_rate:.0%})"
    )
    assert result.spec_endpoints == 6


@pytest.mark.asyncio
async def test_eval_fastapi_notes() -> None:
    """Evaluate against fastapi-notes demo."""
    demo = DemoRepo(
        name="fastapi-notes",
        path="demo/fastapi-notes",
        framework="fastapi",
        expected_endpoints=6,
    )

    if not (PROJECT_ROOT / demo.path).exists():
        pytest.skip("Demo not found")

    result = await evaluate_repo(demo, PROJECT_ROOT)

    assert result.framework_correct, f"Expected fastapi, got {result.framework_detected}"
    assert result.endpoint_detection_rate >= 0.8, (
        f"Only detected {result.endpoints_detected}/{result.endpoints_expected} "
        f"({result.endpoint_detection_rate:.0%})"
    )


@pytest.mark.asyncio
async def test_eval_express_users() -> None:
    """Evaluate against express-users-api demo."""
    demo = DemoRepo(
        name="express-users-api",
        path="demo/express-users-api",
        framework="express",
        expected_endpoints=6,
    )

    if not (PROJECT_ROOT / demo.path).exists():
        pytest.skip("Demo not found")

    result = await evaluate_repo(demo, PROJECT_ROOT)

    assert result.framework_correct, f"Expected express, got {result.framework_detected}"
    assert result.endpoint_detection_rate >= 0.8, (
        f"Only detected {result.endpoints_detected}/{result.endpoints_expected} "
        f"({result.endpoint_detection_rate:.0%})"
    )


# === Integration: evaluate all demos at once ===

@pytest.mark.asyncio
async def test_evaluate_all() -> None:
    """Run the full evaluation harness against all 3 demo repos.

    This is the primary Phase 6 exit criteria test.
    """
    summary = await evaluate_all(PROJECT_ROOT)

    # Print report for visibility
    report = format_report(summary)
    print("\n" + report)

    # Assertions
    assert summary.total_repos == 3, f"Expected 3 repos, got {summary.total_repos}"
    assert summary.framework_accuracy == 1.0, (
        f"Framework accuracy: {summary.framework_accuracy:.0%}"
    )
    assert summary.avg_detection_rate >= 0.8, (
        f"Avg detection rate: {summary.avg_detection_rate:.0%}"
    )
    assert summary.repos_passed == 3, (
        f"Only {summary.repos_passed}/3 repos passed the 80% threshold"
    )


# === Cross-project: evaluate checkpoint-runtime ===

CHECKPOINT_PATH = Path(r"C:\Users\jasim\Documents\Islamic\checkpoint")


@pytest.mark.asyncio
async def test_eval_checkpoint_runtime() -> None:
    """Evaluate against checkpoint-runtime — a real production FastAPI project.

    This proves test-guardian works on non-trivial, real-world codebases,
    not just toy demos. The checkpoint-runtime has 33+ endpoints across
    runs, checkpoints, workers, metrics, and demo namespaces.
    """
    if not CHECKPOINT_PATH.exists():
        pytest.skip("checkpoint-runtime not found")

    demo = DemoRepo(
        name="checkpoint-runtime",
        path=str(CHECKPOINT_PATH),
        framework="fastapi",
        expected_endpoints=33,
        absolute=True,
    )

    result = await evaluate_repo(demo, PROJECT_ROOT)

    # Framework detection
    assert result.framework_correct, (
        f"Expected fastapi, got {result.framework_detected}"
    )

    # Endpoint detection — must catch 80%+ of the 33 endpoints
    assert result.endpoint_detection_rate >= 0.8, (
        f"Only detected {result.endpoints_detected}/{result.endpoints_expected} "
        f"({result.endpoint_detection_rate:.0%})"
    )

    # Print results for visibility
    print(f"\nCheckpoint-runtime: {result.endpoints_detected}/{result.endpoints_expected} "
          f"endpoints ({result.endpoint_detection_rate:.0%})")
    for ep in sorted(result.details["endpoints"], key=lambda e: e["path"]):
        print(f"  {ep['method']:8s} {ep['path']}")


@pytest.mark.asyncio
async def test_evaluate_full_with_checkpoint() -> None:
    """Run the full evaluation including the checkpoint-runtime project.

    This is the ultimate test: 3 toy demos + 1 production project,
    all passing the 80% detection threshold.
    """
    if not CHECKPOINT_PATH.exists():
        pytest.skip("checkpoint-runtime not found")

    summary = await evaluate_full(PROJECT_ROOT)

    report = format_report(summary)
    print("\n" + report)

    # All 4 repos should pass
    assert summary.total_repos == 4, f"Expected 4 repos, got {summary.total_repos}"
    assert summary.framework_accuracy == 1.0, (
        f"Framework accuracy: {summary.framework_accuracy:.0%}"
    )
    assert summary.avg_detection_rate >= 0.8, (
        f"Avg detection rate: {summary.avg_detection_rate:.0%}"
    )
    assert summary.repos_passed == 4, (
        f"Only {summary.repos_passed}/4 repos passed the 80% threshold"
    )
