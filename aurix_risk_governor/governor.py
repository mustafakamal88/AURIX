from __future__ import annotations

from typing import Any, Optional

from aurix_bridge_server.models import Command

from .checks import evaluate_command
from .config import RiskConfig
from .models import RiskDecision


class RiskGovernor:
    def __init__(self, config: RiskConfig):
        self.config = config

    def evaluate_open_market(
        self,
        command: Command,
        snapshot: Optional[dict[str, Any]],
        previous_decisions: list[dict[str, Any]],
    ) -> RiskDecision:
        reasons, context = evaluate_command(command, snapshot, self.config, previous_decisions)
        approved = len(reasons) == 0

        return RiskDecision(
            approved=approved,
            decision="APPROVE" if approved else "BLOCK",
            reasons=reasons,
            command_id=command.id,
            symbol=command.symbol,
            direction=command.direction,
            requested_volume=command.volume,
            approved_volume=command.volume if approved else None,
            spread_points=context.get("spread_points"),
            open_positions=int(context.get("open_positions") or 0),
            equity=context.get("equity"),
            balance=context.get("balance"),
        )
