from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_event_bus import AurixEventBus, AurixEventType, load_event_bus_config
from aurix_strategy_agents import StrategyAgentEvaluator, StrategyAgentRegistry, load_strategy_agent_config
from aurix_strategy_agents.config import StrategyAgentConfigEntry, StrategyAgentsConfig


def v1_signal(decision_trace: bool = False) -> dict[str, Any]:
    signal = {
        "id": "sig-v1",
        "strategy_name": "xauusd_paper_v1",
        "strategy_version": "0.1.0",
        "mode": "PAPER",
        "symbol": "XAUUSDm",
        "direction": "BUY",
        "status": "PAPER_SIGNAL",
        "confidence": 0.72,
        "entry_reference": 2300.1,
        "stop_loss_reference": 2299.0,
        "take_profit_reference": 2302.0,
        "reasons": ["mock signal"],
        "command_id": None,
    }
    if decision_trace:
        signal["decision_trace"] = {"rule": "passed", "candle_time": 1}
    return signal


def v2_skipped() -> dict[str, Any]:
    return {
        "id": "sig-v2",
        "strategy_name": "xauusd_paper_v2",
        "strategy_version": "0.2.0",
        "mode": "PAPER",
        "symbol": "XAUUSDm",
        "direction": None,
        "status": "SKIPPED_SESSION",
        "confidence": 0.0,
        "reasons": ["session blocked"],
        "command_id": None,
    }


def make_evaluator(tmpdir: str, config: StrategyAgentsConfig, signals: list[dict[str, Any]]) -> StrategyAgentEvaluator:
    event_bus = AurixEventBus(tmpdir, load_event_bus_config())
    registry = StrategyAgentRegistry(config)
    return StrategyAgentEvaluator(
        data_dir=tmpdir,
        config=config,
        registry=registry,
        event_bus=event_bus,
        latest_signals=lambda: signals,
        candles=lambda: [],
        context=lambda: {"session_name": "TEST", "session_allowed": False},
    )


def assert_safety_false(status: dict[str, Any]) -> None:
    if status.get("paper_trade_creation_allowed") is not False:
        raise AssertionError(f"paper creation safety wrong: {status}")
    if status.get("order_request_creation_allowed") is not False:
        raise AssertionError(f"order request safety wrong: {status}")
    if status.get("live_execution_allowed") is not False:
        raise AssertionError(f"live execution safety wrong: {status}")
    if status.get("command_queueing_allowed") is not False:
        raise AssertionError(f"command queueing safety wrong: {status}")


def main() -> int:
    config = load_strategy_agent_config()
    if not config.enabled or config.allow_live_execution or config.allow_command_queueing:
        raise AssertionError(f"config did not load safely: {config}")
    registry = StrategyAgentRegistry(config)
    agent_ids = [agent.id for agent in registry.list_registered_agents()]
    if "xauusd_paper_v1_adapter" not in agent_ids or "xauusd_paper_v2_adapter" not in agent_ids:
        raise AssertionError(f"registry missing V1/V2 adapters: {agent_ids}")

    with tempfile.TemporaryDirectory() as tmpdir:
        disabled_config = StrategyAgentsConfig(
            registered_agents=[
                StrategyAgentConfigEntry(id="xauusd_paper_v1_adapter", enabled=True, source_strategy="xauusd_paper_v1"),
                StrategyAgentConfigEntry(id="xauusd_paper_v2_adapter", enabled=False, source_strategy="xauusd_paper_v2"),
            ]
        )
        evaluator = make_evaluator(tmpdir, disabled_config, [v1_signal(), v2_skipped()])
        results = evaluator.evaluate_all_agents()
        if [result.agent_id for result in results] != ["xauusd_paper_v1_adapter"]:
            raise AssertionError(f"disabled agent was evaluated: {results}")

    with tempfile.TemporaryDirectory() as tmpdir:
        trades_file = Path(tmpdir) / "paper_trades.json"
        commands_file = Path(tmpdir) / "commands.json"
        trades_file.write_text("[]", encoding="utf-8")
        commands_file.write_text("[]", encoding="utf-8")
        evaluator = make_evaluator(tmpdir, config, [v1_signal(True), v2_skipped()])
        results = evaluator.evaluate_all_agents()
        if json.loads(trades_file.read_text(encoding="utf-8")):
            raise AssertionError("evaluating agents created paper trades")
        if json.loads(commands_file.read_text(encoding="utf-8")):
            raise AssertionError("evaluating agents queued commands or order requests")
        if not all(result.event_id for result in results):
            raise AssertionError(f"evaluation events were not published: {results}")
        v1 = next(result for result in results if result.agent_id == "xauusd_paper_v1_adapter")
        if v1.status != "SIGNAL" or not v1.decision_trace:
            raise AssertionError(f"V1 signal with decision trace was not adapted: {v1}")
        v2 = next(result for result in results if result.agent_id == "xauusd_paper_v2_adapter")
        if v2.status != "SKIPPED" or not v2.rejection_reasons:
            raise AssertionError(f"V2 skipped result was not adapted: {v2}")
        events = evaluator.event_bus.load_recent_events(20)
        if not any(event.get("event_type") == AurixEventType.STRATEGY_EVALUATION_EVENT.value for event in events):
            raise AssertionError("strategy evaluation event was not published")
        signal_events = [event for event in events if event.get("event_type") == AurixEventType.SIGNAL_EVENT.value]
        if not signal_events:
            raise AssertionError("signal event was not published for mock signal")
        if signal_events[-1].get("payload", {}).get("command_id") is not None:
            raise AssertionError(f"signal event command_id was not null: {signal_events[-1]}")
        assert_safety_false(evaluator.status())
        status = evaluator.status()
        if not status.get("latest_exists") or status.get("latest_status_counts", {}).get("SIGNAL") != 1:
            raise AssertionError(f"latest status was not updated after evaluation: {status}")
        reset = evaluator.reset()
        if reset.get("latest_exists"):
            raise AssertionError(f"reset failed: {reset}")

    with tempfile.TemporaryDirectory() as tmpdir:
        evaluator = make_evaluator(tmpdir, config, [v1_signal(False)])
        result = evaluator.evaluate_agent("xauusd_paper_v1_adapter")
        if result.status != "SIGNAL" or result.decision_trace is not None:
            raise AssertionError(f"V1 legacy signal adaptation failed: {result}")

    for path in (PROJECT_ROOT / "aurix_strategy_agents").rglob("*.py"):
        if "/commands/open-market" in path.read_text(encoding="utf-8"):
            raise AssertionError(f"forbidden command endpoint reference introduced in {path}")

    for config_path in [
        PROJECT_ROOT / "config/live_readiness.yaml",
        PROJECT_ROOT / "config/evidence_monitor.yaml",
        PROJECT_ROOT / "config/signal_certifier.yaml",
        PROJECT_ROOT / "config/paper_risk_audit.yaml",
        PROJECT_ROOT / "config/event_bus.yaml",
        PROJECT_ROOT / "config/strategy_agents.yaml",
    ]:
        text = config_path.read_text(encoding="utf-8")
        for required in ["allow_live_arming: false", "allow_live_execution: false", "allow_command_queueing: false"]:
            if required not in text:
                raise AssertionError(f"{config_path} missing {required}")

    print("OK: strategy agent self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
