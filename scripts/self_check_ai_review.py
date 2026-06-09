from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_ai_review import AIReviewConfig, AIReviewTemplateReviewer


def main() -> int:
    reviewer = AIReviewTemplateReviewer(AIReviewConfig())

    empty = reviewer.generate({})
    if "Not enough performance data" not in empty.summary:
        raise AssertionError(f"empty review should mention not enough performance data: {empty.summary}")
    if empty.safety.get("external_llm_used") is not False or empty.safety.get("commands_queued") is not False:
        raise AssertionError(f"safety flags wrong: {empty.safety}")

    inputs: dict[str, Any] = {
        "journal_entries": [
            {"classification": "SESSION_BLOCKED", "mistake_flags": ["NONE"]},
            {"classification": "SESSION_BLOCKED", "mistake_flags": ["NONE"]},
        ],
        "analytics_report": {
            "total_trades": 0,
            "closed_trades": 0,
            "warnings": ["no closed paper trades yet"],
        },
        "market_quality": {"ok": True},
        "signals": [{"id": "s1"}, {"id": "s2"}],
        "paper_trades": [],
    }
    report = reviewer.generate(inputs)
    joined = " ".join(report.behaviour_observations + report.mistake_patterns + report.action_items)
    if "respecting session rules" not in joined:
        raise AssertionError(f"session blocked pattern not detected: {report.behaviour_observations}")
    if not any("no closed paper trades yet" in item for item in report.mistake_patterns):
        raise AssertionError(f"analytics warnings missing: {report.mistake_patterns}")
    if "Continue paper-forward testing during active sessions." not in report.action_items:
        raise AssertionError(f"no-trade action item missing: {report.action_items}")
    if report.safety != {
        "review_only": True,
        "no_execution": True,
        "no_strategy_mutation": True,
        "external_llm_used": False,
        "commands_queued": False,
    }:
        raise AssertionError(f"safety flags changed: {report.safety}")

    closed = reviewer.generate(
        {
            "analytics_report": {
                "total_trades": 3,
                "closed_trades": 3,
                "win_rate": 0.5,
                "total_r": 1.2,
                "expectancy_r": 0.4,
                "max_consecutive_losses": 2,
            },
            "market_quality": {"ok": True},
            "paper_trades": [{"id": "t1"}],
        }
    )
    if "win_rate=0.5" not in closed.summary or not any("Max consecutive losses=2" in item for item in closed.performance_observations):
        raise AssertionError(f"closed trade metrics missing: {closed}")

    print("OK: AI review self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
