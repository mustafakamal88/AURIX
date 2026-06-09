from __future__ import annotations

from .models import AurixAutonomyMode, AurixDecisionAction


def apply_autonomy(autonomy_level: str, action: AurixDecisionAction) -> AurixDecisionAction:
    if autonomy_level == AurixAutonomyMode.OBSERVE_ONLY.value and action in {AurixDecisionAction.TRADE_LONG, AurixDecisionAction.TRADE_SHORT}:
        return AurixDecisionAction.WAIT
    if autonomy_level in {AurixAutonomyMode.DEMO_AUTONOMY_DISABLED.value, AurixAutonomyMode.MICRO_LIVE_DISABLED.value} and action in {AurixDecisionAction.TRADE_LONG, AurixDecisionAction.TRADE_SHORT}:
        return AurixDecisionAction.MANUAL_MODE_REQUIRED
    return action
