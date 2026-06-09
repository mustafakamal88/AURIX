from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aurix_paper_risk_audit import PaperRiskAuditConfig, PaperRiskAuditStore, PaperRiskDecision
from aurix_signal_certifier import SignalCertifierConfig, SignalPathCertifier


def decision() -> PaperRiskDecision:
    return PaperRiskDecision(
        symbol="XAUUSDm",
        strategy_name="xauusd_paper_v1",
        strategy_version="0.1.0",
        signal_id="sig-1",
        trade_id="trade-1",
        direction="BUY",
        entry_reference=100.0,
        stop_loss_reference=97.0,
        take_profit_reference=106.0,
        volume=0.01,
        risk_status="APPROVED",
        risk_reason="simulated risk approved",
        checks={"risk_governor_approved": True},
        limits={"default_volume": 0.01},
        account_snapshot={"currency": "GBP"},
        market_snapshot={"symbol": "XAUUSDm", "bid": 99.9, "ask": 100.0},
        safety={"mt5_commands_queued": False, "broker_order_created": False},
    )


def certifier_inputs(with_decision: bool = True) -> dict:
    d = decision().model_dump()
    return {
        "latest_snapshot": {"account": {"currency": "GBP"}, "tick": {"symbol": "XAUUSDm", "bid": 99.9, "ask": 100.0, "spread_points": 10}},
        "strategy_signals": [
            {
                "id": "sig-1",
                "strategy_name": "xauusd_paper_v1",
                "strategy_version": "0.1.0",
                "mode": "PAPER",
                "symbol": "XAUUSDm",
                "direction": "BUY",
                "status": "SHADOW_SIGNAL",
                "command_id": None,
                "risk_checked": False,
                "paper_risk_checked": with_decision,
                "paper_risk_decision_id": d["id"] if with_decision else None,
                "paper_risk_status": "APPROVED" if with_decision else None,
                "context_session": "LONDON",
                "context_regime": "RANGE",
                "context_bias": "NEUTRAL",
                "range_high": 105.0,
                "range_low": 100.0,
                "reasons": ["previous candle swept range low", "current bullish candle reclaimed range low"],
            }
        ],
        "paper_trades": [
            {
                "id": "trade-1",
                "signal_id": "sig-1",
                "strategy_name": "xauusd_paper_v1",
                "strategy_version": "0.1.0",
                "symbol": "XAUUSDm",
                "direction": "BUY",
                "status": "OPEN",
                "entry_price": 100.0,
                "stop_loss": 97.0,
                "take_profit": 106.0,
                "volume": 0.01,
                "opened_at": "2026-06-09T00:00:00+00:00",
                "risk_decision_id": d["id"] if with_decision else None,
                "reasons": ["created from shadow signal"],
            }
        ],
        "paper_risk_decisions": [d] if with_decision else [],
        "paper_analytics": {"open_trades": 1, "closed_trades": 0, "expectancy_r": 0.0},
        "operator_status": {"commands": {"open_count": 0}, "bridge": {"positions_count": 0}, "safety": {"ea_allow_live_trading_seen": False}},
        "operator_summary": {"mode": "PAPER", "paper_open_count": 1},
        "live_readiness_report": {"live_execution_allowed": False, "live_arming_allowed": False},
        "paper_config": {"enabled": True, "max_open_paper_trades": 1, "allow_multiple_same_direction": False, "default_stop_points": 300, "default_take_profit_points": 600},
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    config = PaperRiskAuditConfig()
    require(config.allow_live_arming is False, "live arming must remain false")
    require(config.allow_live_execution is False, "live execution must remain false")
    require(config.allow_command_queueing is False, "command queueing must remain false")

    with TemporaryDirectory() as tmp:
        store = PaperRiskAuditStore(tmp, config)
        status = store.status()
        require(status["decision_count"] == 0, "empty audit store not handled")
        saved = store.add_decision(decision())
        require(saved["mode"] == "PAPER", "decision mode should be PAPER")
        require(saved["signal_id"] == "sig-1" and saved["trade_id"] == "trade-1", "decision links wrong ids")
        require(len(store.list_decisions()) == 1, "decision not persisted")
        require(len(store.history()) == 1, "history append failed")

    report = SignalPathCertifier(SignalCertifierConfig()).certify(certifier_inputs(with_decision=True))
    require("paper risk decision was not persisted" not in report.warnings, "persisted decision still warned missing")
    require("paper risk decision links certified signal" in report.passed_checks, "certifier did not read paper risk decision")

    legacy = SignalPathCertifier(SignalCertifierConfig()).certify(certifier_inputs(with_decision=False))
    require("paper risk decision was not persisted" in legacy.warnings, "legacy missing decision warning missing")

    for file in Path("aurix_paper_risk_audit").glob("*.py"):
        text = (ROOT / file).read_text(encoding="utf-8")
        require("commands/open-market" not in text, f"forbidden endpoint reference in {file}")
        require("add_command" not in text, f"command queueing reference in {file}")

    print("OK: paper risk audit self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
