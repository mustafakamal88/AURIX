from __future__ import annotations

from typing import Any

from .config import LiveReadinessConfig


def build_manual_checklist(config: LiveReadinessConfig) -> list[str]:
    return [
        "confirm GitHub checkpoint pushed",
        "confirm live trading disabled",
        "confirm EA AURIX_BROKER_EXECUTION=false",
        "confirm evidence gate not blocked",
        f"confirm {config.require_min_closed_paper_trades}+ closed paper trades",
        f"confirm {config.require_min_forward_days}+ forward-test days",
        "confirm no open commands",
        "confirm no open paper trades",
        "confirm risk config for micro-live prepared but inactive",
        "confirm manual human approval required",
    ]


def build_micro_live_plan(config: LiveReadinessConfig) -> dict[str, Any]:
    return {
        "built": False,
        "status": "NOT_BUILT",
        "inactive": True,
        "max_volume": config.micro_live_max_volume,
        "max_daily_loss_amount": config.micro_live_max_daily_loss_amount,
        "max_trades_per_day": config.micro_live_max_trades_per_day,
        "requires_new_branch": config.micro_live_requires_new_branch,
        "requires_manual_human_approval": config.require_manual_human_approval,
        "notes": [
            "micro-live execution is not implemented in Part 23",
            "this plan is a readiness checklist only",
        ],
    }
