from __future__ import annotations

from .models import AurixRuntimeState, EventSafety


def initial_runtime_state(symbol: str = "XAUUSDm", mode: str = "EVENT_BUS_ONLY") -> AurixRuntimeState:
    return AurixRuntimeState(
        symbol=symbol,
        mode=mode,
        market={},
        account={},
        positions={"items": [], "latest": None},
        orders={"items": [], "latest": None},
        trade_history={"items": [], "latest": None},
        session={},
        context={},
        strategy={},
        risk={},
        execution={"latest_order_event": None},
        paper={"open_count": 0, "closed_count": 0, "latest_trade": None},
        journal={},
        alerts={},
        safety=EventSafety().model_dump(),
        health={},
    )
