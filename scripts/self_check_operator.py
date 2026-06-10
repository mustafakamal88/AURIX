from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_bridge_server.store import JsonStore
from aurix_context_engine import ContextEngine
from aurix_context_engine.config import ContextConfig
from aurix_market_data import MarketDataRecorder
from aurix_market_data.config import MarketDataConfig
from aurix_operator import build_operator_summary, build_operator_status
from aurix_paper_trading import PaperLedger, PaperTradingEngine
from aurix_paper_trading.config import PaperTradingConfig
from aurix_risk_governor.config import RiskConfig
from aurix_supervisor import PaperSupervisor, SupervisorConfig
from aurix_strategy_engine import StrategyEngine
from aurix_strategy_engine.config import StrategyConfig
from aurix_strategy_engine.xauusd_paper_v1 import XauusdPaperV1Config


def candle(index: int) -> dict[str, Any]:
    close = 2300.0 + (index * 0.01)
    return {
        "time": index,
        "open": close - 0.1,
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "tick_volume": 20,
        "spread": 20,
        "real_volume": 0,
    }


def snapshot() -> dict[str, Any]:
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        "account": {"balance": 10000.0, "equity": 10025.0, "currency": "USD"},
        "tick": {
            "symbol": "XAUUSDm",
            "bid": 2300.0,
            "ask": 2300.2,
            "point": 0.01,
            "spread_points": 20,
            "time": 123456,
        },
        "candles": [candle(i) for i in range(30)],
        "positions": [],
        "orders": [],
        "deals": [],
        "raw": {"broker_execution_enabled": False},
    }


def make_status(tmpdir: str, store: JsonStore) -> tuple[dict[str, Any], dict[str, Any]]:
    market_config = MarketDataConfig(max_snapshot_age_seconds=10, max_spread_points=100, min_candles_required=20)
    market_recorder = MarketDataRecorder(tmpdir, market_config)
    context_engine = ContextEngine(tmpdir, ContextConfig(max_spread_points=100, min_candles_required=20))
    paper_ledger = PaperLedger(tmpdir)
    risk_config = RiskConfig(max_spread_points=100, max_volume=0.01)
    paper_engine = PaperTradingEngine(PaperTradingConfig(symbol="XAUUSDm"), risk_config)
    supervisor = PaperSupervisor(
        data_dir=tmpdir,
        config=SupervisorConfig(),
        store=store,
        market_recorder=market_recorder,
        context_engine=context_engine,
        xauusd_paper_v1_config=XauusdPaperV1Config(symbol="XAUUSDm"),
        paper_engine=paper_engine,
        paper_ledger=paper_ledger,
        market_config=market_config,
    )
    strategy_engine = StrategyEngine(StrategyConfig(symbol="XAUUSDm"))
    snap = store.latest_snapshot()
    if snap:
        market_recorder.record_snapshot(snap)
        context = context_engine.evaluate(snap, market_recorder.list_candles(), market_recorder.quality())
        context_engine.store(context)

    risk_status = {
        "enabled": risk_config.enabled,
        "can_trade": snap is not None,
        "reasons": [] if snap else ["account snapshot missing", "tick missing", "spread missing"],
    }
    status = build_operator_status(
        service="aurix-mac-wine-bridge",
        terminal_id="AURIX-MAC-001",
        store=store,
        market_recorder=market_recorder,
        market_config=market_config,
        context_engine=context_engine,
        risk_status=risk_status,
        strategy_status=strategy_engine.status(snap, store.list_strategy_signals()),
        paper_status=paper_engine.status(snap, paper_ledger.list_trades()),
        supervisor_status=supervisor.status().model_dump(),
    )
    return status.model_dump(), build_operator_summary(status).model_dump()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonStore(tmpdir)

        def fail_add_command(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("operator status must not queue commands")

        store.add_command = fail_add_command  # type: ignore[method-assign]
        missing_status, missing_summary = make_status(tmpdir, store)
        if missing_status["bridge"]["snapshot_received"]:
            raise AssertionError("missing snapshot should be reported as missing")
        if missing_summary["ok"] or "snapshot missing" not in missing_summary["warnings"]:
            raise AssertionError(f"missing snapshot should not be ok, got {missing_summary}")

        store.save_snapshot(snapshot())
        healthy_status, healthy_summary = make_status(tmpdir, store)
        if not healthy_summary["ok"]:
            raise AssertionError(f"healthy snapshot should be ok, got {healthy_summary}")
        safety = healthy_status["safety"]
        if safety["live_trading_enabled"] is not False or safety["paper_only"] is not True:
            raise AssertionError(f"safety flags wrong: {safety}")
        if safety["ea_broker_execution_seen"] is not False:
            raise AssertionError(f"EA live trading flag should be false, got {safety}")
        if store.list_commands():
            raise AssertionError("operator status queued commands")

    print("OK: operator self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
