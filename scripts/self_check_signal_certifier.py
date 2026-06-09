from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aurix_signal_certifier import SignalCertifierConfig, SignalCertifierStore, SignalPathCertifier


def sample(command_id=None, linked=True, live_exec=False, live_arm=False, open_commands=0, risk_persisted=False, decision_trace: str | None = None) -> dict:
    signal_id = "sig-1"
    trade = {
        "id": "trade-1",
        "signal_id": signal_id if linked else "missing",
        "strategy_name": "xauusd_paper_v1",
        "strategy_version": "0.1.0",
        "symbol": "XAUUSDm",
        "direction": "BUY",
        "status": "OPEN",
        "entry_price": 100.3,
        "stop_loss": 97.3,
        "take_profit": 106.3,
        "volume": 0.01,
        "opened_at": "2026-06-09T06:12:31+00:00",
        "reasons": ["created from shadow signal", "previous candle swept range low", "current bullish candle reclaimed range low"],
    }
    signal = {
        "id": signal_id,
        "strategy_name": "xauusd_paper_v1",
        "strategy_version": "0.1.0",
        "mode": "PAPER",
        "symbol": "XAUUSDm",
        "direction": "BUY",
        "status": "SHADOW_SIGNAL",
        "command_id": command_id,
        "risk_checked": False,
        "context_session": "LONDON",
        "context_regime": "RANGE",
        "context_bias": "NEUTRAL",
        "range_high": 105.0,
        "range_low": 100.0,
        "reasons": ["previous candle swept range low", "current bullish candle reclaimed range low"],
    }
    if decision_trace:
        signal["decision_trace"] = {
            "trace_version": "1.0",
            "strategy": "xauusd_paper_v1",
            "strategy_version": "0.1.0",
            "created_at": "2026-06-09T06:12:30+00:00",
            "snapshot_updated_at": "2026-06-09T06:12:30+00:00",
            "symbol": "XAUUSDm",
            "direction": "BUY",
            "session": "LONDON",
            "regime": "RANGE",
            "bias": "NEUTRAL",
            "range_high": 105.0,
            "range_low": 100.0,
            "spread_points": 30,
            "max_spread_points": 350,
            "previous_candle": {"time": 1, "open": 101, "high": 102, "low": 99, "close": 99.5},
            "current_candle": {"time": 2, "open": 99.8, "high": 101, "low": 99.2, "close": 100.5},
            "rule_name": "range_low_sweep_reclaim_buy",
            "rule_checks": {
                "allow_buy": True,
                "symbol_matched": True,
                "session_allowed": True,
                "spread_ok": True,
                "enough_candles": True,
                "cooldown_ok": True,
                "previous_low_lt_range_low": decision_trace != "invalid",
                "current_close_gt_range_low": True,
                "current_candle_bullish": True,
            },
        }
    return {
        "latest_snapshot": {
            "received_at": "2026-06-09T06:12:30+00:00",
            "account": {"currency": "GBP"},
            "tick": {"symbol": "XAUUSDm", "bid": 100.0, "ask": 100.3, "spread_points": 30, "point": 0.01},
            "candles": [{"open": 101, "high": 102, "low": 99, "close": 99.5}, {"open": 99.8, "high": 101, "low": 99.2, "close": 100.5}],
        },
        "market_candles": [{"open": 101, "high": 102, "low": 99, "close": 99.5}, {"open": 99.8, "high": 101, "low": 99.2, "close": 100.5}],
        "strategy_signals": [signal],
        "paper_trades": [trade],
        "paper_analytics": {"open_trades": 1, "closed_trades": 0, "expectancy_r": 0.0},
        "operator_status": {"commands": {"open_count": open_commands}, "bridge": {"positions_count": 0}, "safety": {"ea_allow_live_trading_seen": False}},
        "operator_summary": {"mode": "PAPER", "paper_open_count": 1},
        "live_readiness_report": {"status": "BLOCKED", "live_execution_allowed": live_exec, "live_arming_allowed": live_arm},
        "evidence_growth_report": {"status": "COLLECTING"},
        "risk_decisions": [{"command_id": "trade-1"}] if risk_persisted else [],
        "paper_config": {"enabled": True, "max_open_paper_trades": 1, "allow_multiple_same_direction": False, "default_stop_points": 300, "default_take_profit_points": 600},
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    config = SignalCertifierConfig()
    certifier = SignalPathCertifier(config)

    no_signal = certifier.certify({})
    require(no_signal.status == "NO_SIGNAL", f"no signal should be NO_SIGNAL, got {no_signal.status}")

    legacy = certifier.certify(sample())
    require(legacy.status == "CERTIFIED_WITH_WARNINGS", f"legacy missing trace should certify with warnings, got {legacy.status} {legacy.failed_checks}")
    require("legacy signal missing decision-time OHLC/rule trace" in legacy.warnings, "legacy trace warning missing")
    require(any("legacy_signal_trace_missing" in item for item in legacy.skipped_checks), "legacy V1 rule checks were not skipped")
    require(not any(item.startswith("V1 BUY rule") for item in legacy.failed_checks), "legacy V1 rule checks should not fail")

    valid = certifier.certify(sample(decision_trace="valid"))
    require(valid.status in {"CERTIFIED", "CERTIFIED_WITH_WARNINGS"}, f"valid traced trade not certified: {valid.status} {valid.failed_checks}")
    require("signal risk_checked=false even though paper engine simulated risk before ledger write" in valid.warnings, "risk_checked warning missing")
    require("paper risk decision was not persisted in data/risk_decisions.json" in valid.warnings, "missing persisted risk warning missing")
    require(any("persist paper simulation risk decisions" in item for item in valid.recommendations), "risk persistence recommendation missing")

    invalid = certifier.certify(sample(decision_trace="invalid"))
    require(invalid.status == "FAILED", "invalid decision_trace should fail")
    require("V1 BUY rule previous_low_lt_range_low" in invalid.failed_checks, "invalid trace failed check missing")

    missing = certifier.certify(sample(linked=False))
    require(missing.status == "FAILED", "missing signal link should fail")

    command = certifier.certify(sample(command_id="cmd-1"))
    require(command.status == "FAILED", "non-null command_id should fail")

    unsafe_exec = certifier.certify(sample(live_exec=True))
    require(unsafe_exec.status == "FAILED", "unsafe live execution should fail")

    unsafe_arm = certifier.certify(sample(live_arm=True))
    require(unsafe_arm.status == "FAILED", "unsafe live arming should fail")

    open_command = certifier.certify(sample(open_commands=1))
    require(open_command.status == "FAILED", "open command presence should fail")

    require(valid.safety.get("certification_only") is True, "certification safety flag wrong")
    require(valid.safety.get("live_execution_allowed") is False, "live execution safety flag wrong")
    require(valid.safety.get("live_arming_allowed") is False, "live arming safety flag wrong")
    require(valid.safety.get("mt5_commands_queued") is False, "queueing safety flag wrong")
    require(valid.safety.get("broker_order_created") is False, "broker order safety flag wrong")

    with TemporaryDirectory() as tmp:
        store = SignalCertifierStore(tmp, config)
        report = store.certify(sample(decision_trace="valid"))
        require(report.status in {"CERTIFIED", "CERTIFIED_WITH_WARNINGS"}, "store certify failed")
        require((Path(tmp) / "signal_path_certification_report.json").exists(), "latest report missing")
        require(len(store.history()) == 1, "history append failed")
        store.reset()
        require(store.latest() is None, "reset did not clear latest")
        require(store.history() == [], "reset did not clear history")

    watch_text = (ROOT / "scripts/watch_signal_path.py").read_text(encoding="utf-8")
    require("/signal-certifier/status" in watch_text, "watch mode should read latest status")
    require("/signal-certifier/certify" not in watch_text, "watch mode should not append certification history")

    for file in Path("aurix_signal_certifier").glob("*.py"):
        text = (ROOT / file).read_text(encoding="utf-8")
        require("commands/open-market" not in text, f"forbidden endpoint reference in {file}")
        require("add_command" not in text, f"command queueing reference in {file}")

    print("OK: signal certifier self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
