from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_bridge_server.store import JsonStore
from aurix_context_engine import ContextEngine
from aurix_context_engine.config import ContextConfig
from aurix_market_data import MarketDataRecorder
from aurix_market_data.config import MarketDataConfig
from aurix_paper_trading import PaperLedger, PaperTradingEngine
from aurix_paper_trading.config import PaperTradingConfig
from aurix_risk_governor.config import RiskConfig
from aurix_strategy_engine.xauusd_paper_v1 import XauusdPaperV1Config
from aurix_supervisor import PaperSupervisor, SupervisorConfig


def candle(index: int, close: float = 2300.0) -> dict:
    return {
        "time": index,
        "open": close - 0.2,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "tick_volume": 20,
        "spread": 20,
        "real_volume": 0,
    }


def snapshot(spread: float = 20, age_seconds: float = 0) -> dict:
    received_at = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    candles = [candle(i, 2300.0 + (i * 0.01)) for i in range(30)]
    return {
        "terminal_id": "AURIX-MAC-001",
        "received_at": received_at,
        "account": {"balance": 10000.0, "equity": 10000.0},
        "tick": {
            "symbol": "XAUUSDm",
            "bid": 2300.0,
            "ask": 2300.2,
            "point": 0.01,
            "spread_points": spread,
            "time": 123456,
        },
        "candles": candles,
        "positions": [],
        "orders": [],
        "deals": [],
    }


def build_supervisor(tmpdir: str, require_quality: bool = True) -> tuple[PaperSupervisor, JsonStore]:
    store = JsonStore(tmpdir)
    market_config = MarketDataConfig(max_snapshot_age_seconds=10, max_spread_points=100, min_candles_required=20)
    market_recorder = MarketDataRecorder(tmpdir, market_config)
    context_engine = ContextEngine(tmpdir, ContextConfig(max_spread_points=100, min_candles_required=20))
    paper_ledger = PaperLedger(tmpdir)
    paper_engine = PaperTradingEngine(
        PaperTradingConfig(symbol="XAUUSDm", default_volume=0.01, max_open_paper_trades=1),
        RiskConfig(max_spread_points=100, max_volume=0.01),
    )
    supervisor = PaperSupervisor(
        data_dir=tmpdir,
        config=SupervisorConfig(require_market_quality_ok=require_quality, max_snapshot_age_seconds=10),
        store=store,
        market_recorder=market_recorder,
        context_engine=context_engine,
        xauusd_paper_v1_config=XauusdPaperV1Config(symbol="XAUUSDm", max_spread_points=100, min_candles=20),
        paper_engine=paper_engine,
        paper_ledger=paper_ledger,
        market_config=market_config,
    )
    return supervisor, store


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        supervisor, store = build_supervisor(tmpdir)

        missing = supervisor.run_once()
        if missing.loop_count != 1 or "snapshot missing" not in missing.errors:
            raise AssertionError(f"missing snapshot should not crash and should be reported, got {missing}")

        store.save_snapshot(snapshot(spread=500))
        high_spread = supervisor.run_once()
        if high_spread.market_quality_ok or high_spread.strategy_signal_id is not None:
            raise AssertionError(f"high spread should block required-quality strategy pipeline, got {high_spread}")

        if store.list_commands():
            raise AssertionError("supervisor queued a command during high spread check")

        store.save_snapshot(snapshot(spread=20))
        status = supervisor.run_once()
        if store.list_commands():
            raise AssertionError("supervisor queued a command during run-once")
        if status.safety.get("allow_command_queueing") is not False or status.safety.get("mt5_commands_queued") is not False:
            raise AssertionError(f"supervisor safety flags wrong: {status.safety}")

        status_file = Path(tmpdir) / "supervisor_status.json"
        if not status_file.exists():
            raise AssertionError("supervisor status file was not saved")
        saved = json.loads(status_file.read_text(encoding="utf-8"))
        if saved.get("loop_count") != status.loop_count:
            raise AssertionError(f"saved status mismatch: {saved}")

    print("OK: supervisor self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
