#!/usr/bin/env python3
"""Evaluation runner — run test-guardian against all demo repos.

Usage:
    cd eval && python run_eval.py
"""

import asyncio
import sys
from pathlib import Path

# Add agent source to path
agent_root = Path(__file__).parent.parent / "agent"
sys.path.insert(0, str(agent_root / "src"))

from guardian.eval.harness import evaluate_all, evaluate_full, format_report


async def main() -> None:
    project_root = Path(__file__).parent.parent

    # Use --full flag to include external real-world projects
    full_mode = "--full" in sys.argv
    mode_label = "all repos (including external)" if full_mode else "demo repos"
    print(f"Evaluating test-guardian against {mode_label}")
    print()

    if full_mode:
        summary = await evaluate_full(str(project_root))
    else:
        summary = await evaluate_all(str(project_root))
    report = format_report(summary)
    print(report)

    # Write results to file
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"eval_{timestamp}.txt"
    results_file.write_text(report)
    print(f"\nResults saved to: {results_file}")

    # Exit with appropriate code
    if summary.avg_detection_rate >= 0.8 and summary.framework_accuracy >= 0.8:
        print("\n[PASS] Meets 80% threshold")
        sys.exit(0)
    else:
        print("\n[FAIL] Below 80% threshold")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
