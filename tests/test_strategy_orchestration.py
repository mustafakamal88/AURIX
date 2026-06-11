from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from aurix_decision_engine.config import DecisionEngineConfig
from aurix_decision_engine.engine import AurixDecisionEngine
from aurix_demo_broker_execution import DemoBrokerExecutionStore
from aurix_event_bus import AurixEventBus, load_event_bus_config
from aurix_paper_trading.config import PaperTradingConfig
from aurix_paper_trading.engine import PaperTradingEngine
from aurix_risk_governor.config import RiskConfig
from aurix_strategy_agents import StrategyAgentEvaluator, StrategyAgentRegistry, build_closed_candle_context, detect_raw_timeframe, normalize_candles_for_timeframe
from aurix_strategy_agents.config import StrategyAgentConfigEntry, StrategyAgentsConfig
from aurix_strategy_engine.models import StrategySignal


def contextual_candles(count: int = 80, final_close: float = 110.0) -> list[dict[str, Any]]:
    candles: list[dict[str, Any]] = []
    for index in range(count - 1):
        close = 100.0 + (((index % 5) - 2) * 0.05)
        open_ = 100.0 + ((((index - 1) % 5) - 2) * 0.05) if index else close
        candles.append(
            {
                "symbol": "XAUUSDm",
                "time": 1000 + index * 60,
                "open": open_,
                "high": max(open_, close) + 0.5,
                "low": min(open_, close) - 0.5,
                "close": close,
                "tick_volume": 100,
                "closed": True,
            }
        )
    candles.append(
        {
            "symbol": "XAUUSDm",
            "time": 1000 + (count - 1) * 60,
            "open": 100.0,
            "high": max(100.0, final_close) + 0.5,
            "low": min(100.0, final_close) - 0.5,
            "close": final_close,
            "tick_volume": 100,
            "closed": True,
        }
    )
    return candles


def strategy_m15_candles(count: int = 80, final_close: float = 110.0) -> list[dict[str, Any]]:
    candles: list[dict[str, Any]] = []
    for index in range(count - 1):
        close = 100.0 + (((index % 5) - 2) * 0.05)
        open_ = 100.0 + ((((index - 1) % 5) - 2) * 0.05) if index else close
        candles.append(
            {
                "symbol": "XAUUSDm",
                "time": index * 900,
                "open": open_,
                "high": max(open_, close) + 0.5,
                "low": min(open_, close) - 0.5,
                "close": close,
                "tick_volume": 100,
                "spread": 10,
                "closed": True,
            }
        )
    candles.append(
        {
            "symbol": "XAUUSDm",
            "time": (count - 1) * 900,
            "open": 100.0,
            "high": max(100.0, final_close) + 0.5,
            "low": min(100.0, final_close) - 0.5,
            "close": final_close,
            "tick_volume": 100,
            "spread": 10,
            "closed": True,
        }
    )
    return candles


def m1_candles(minutes: int, *, start: int = 0) -> list[dict[str, Any]]:
    candles: list[dict[str, Any]] = []
    for index in range(minutes):
        open_ = 100.0 + index * 0.1
        close = open_ + 0.05
        candles.append(
            {
                "symbol": "XAUUSDm",
                "time": start + index * 60,
                "open": open_,
                "high": close + 0.2,
                "low": open_ - 0.3,
                "close": close,
                "tick_volume": index + 1,
                "real_volume": index + 2,
                "spread": 5 + (index % 3),
                "closed": True,
            }
        )
    return candles


def strategy_config() -> StrategyAgentsConfig:
    return StrategyAgentsConfig(
        registered_agents=[
            StrategyAgentConfigEntry(id="xauusd_paper_v1_adapter", enabled=True, source_strategy="xauusd_paper_v1"),
            StrategyAgentConfigEntry(id="xauusd_paper_v2_adapter", enabled=True, source_strategy="xauusd_paper_v2"),
            StrategyAgentConfigEntry(id="fast_rsi_first_reversal_v1", enabled=True, source_strategy="fast_rsi_first_reversal", mode="OBSERVATION_ONLY"),
            StrategyAgentConfigEntry(id="blackcat_cloud_v1", enabled=True, source_strategy="blackcat_cloud_v1", mode="OBSERVATION_ONLY"),
        ],
        fast_rsi_first_reversal={"strategy_name": "fast_rsi_first_reversal", "strategy_version": "1.0.0", "max_spread_points": 999},
        blackcat_cloud_v1={"strategy_name": "blackcat_cloud_v1", "strategy_version": "1.0.0", "timeframe": "M15"},
    )


def signal(strategy_name: str, direction: str, confidence: float) -> dict[str, Any]:
    return {
        "id": f"sig-{strategy_name}",
        "strategy_name": strategy_name,
        "strategy_version": "1.0.0",
        "symbol": "XAUUSDm",
        "direction": direction,
        "status": "PAPER_SIGNAL",
        "confidence": confidence,
        "reasons": [f"{strategy_name} candidate"],
        "command_id": None,
    }


class StrategyOrchestrationTests(unittest.TestCase):
    def make_evaluator(self, tmpdir: str, candles: list[dict[str, Any]], signals: list[dict[str, Any]]) -> StrategyAgentEvaluator:
        config = strategy_config()
        registry = StrategyAgentRegistry(config, tmpdir)
        event_bus = AurixEventBus(tmpdir, load_event_bus_config())
        event_bus.get_latest_state = lambda: {  # type: ignore[method-assign]
            "market": {"latest_tick": {"symbol": "XAUUSDm", "bid": 100.0, "ask": 100.2, "point": 0.01, "spread_points": 10}},
            "account": {"currency": "GBP", "balance": 100.0, "equity": 100.0, "margin_free": 100.0},
            "session": {"session_allowed": True},
        }
        return StrategyAgentEvaluator(
            data_dir=tmpdir,
            config=config,
            registry=registry,
            event_bus=event_bus,
            latest_signals=lambda: signals,
            candles=lambda: candles,
            context=lambda: {"session_allowed": True},
        )

    def test_all_four_strategies_same_cycle_same_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = self.make_evaluator(tmpdir, strategy_m15_candles(), [signal("xauusd_paper_v1", "BUY", 0.61), signal("xauusd_paper_v2", "SELL", 0.91)])
            results = evaluator.evaluate_all_agents()
            trace = evaluator.recent_traces(1)[0]

            self.assertEqual(len(results), 4)
            self.assertEqual(trace["strategies_evaluated"], 4)
            self.assertEqual(len(trace["strategy_outputs"]), 4)
            timestamps = {item["latest_closed_candle_timestamp"] for item in trace["strategy_outputs"]}
            self.assertEqual(timestamps, {trace["latest_closed_candle_timestamp"]})
            self.assertTrue(all((item["candle_memory_used"] or 0) >= 25 for item in trace["strategy_outputs"]))

    def test_insufficient_memory_forces_all_wait(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = self.make_evaluator(tmpdir, strategy_m15_candles(24), [signal("xauusd_paper_v1", "BUY", 0.99)])
            results = evaluator.evaluate_all_agents()
            trace = evaluator.recent_traces(1)[0]

            self.assertTrue(all(result.status == "SKIPPED" for result in results))
            self.assertTrue(all("insufficient_strategy_timeframe_candles" in item["reasons"] for item in trace["strategy_outputs"]))
            self.assertEqual(trace["selected_strategy_id"], None)

    def test_unfinished_candle_excluded_from_shared_context(self) -> None:
        candles = contextual_candles()
        candles.append({"time": 999999, "open": 1, "high": 2, "low": 1, "close": 2, "tick_volume": 1, "closed": False})
        context = build_closed_candle_context(candles)

        self.assertNotEqual(context["latest_closed_candle_timestamp"], 999999)
        self.assertTrue(context["ignored_unfinished_candle"])

    def test_structure_and_premium_discount_context(self) -> None:
        candles = strategy_m15_candles(80, final_close=110.0)
        context = build_closed_candle_context(candles)

        self.assertEqual(len(context["candles_25"]), 25)
        self.assertEqual(len(context["candles_50"]), 50)
        self.assertEqual(len(context["candles_100"]), 80)
        self.assertGreater(context["structure_high"], context["structure_low"])
        self.assertEqual(context["premium_discount_state"], "PREMIUM")
        self.assertIn(context["structure_bias"], {"BULLISH", "BEARISH", "BALANCED"})
        self.assertIsInstance(context["bull_power"], float)
        self.assertIsInstance(context["bear_power"], float)

    def test_m1_timeframe_detected_from_sixty_second_steps(self) -> None:
        self.assertEqual(detect_raw_timeframe(m1_candles(30)), "M1")

    def test_m1_resampled_to_closed_m15_candles_with_ohlcv(self) -> None:
        raw = m1_candles(30)
        normalized = normalize_candles_for_timeframe(raw, strategy_timeframe="M15")
        candles = normalized["candles"]

        self.assertTrue(normalized["resampled"])
        self.assertEqual(normalized["raw_timeframe"], "M1")
        self.assertEqual(normalized["strategy_timeframe"], "M15")
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0]["time"], 0)
        self.assertEqual(candles[0]["open"], raw[0]["open"])
        self.assertEqual(candles[0]["close"], raw[14]["close"])
        self.assertEqual(candles[0]["high"], max(item["high"] for item in raw[:15]))
        self.assertEqual(candles[0]["low"], min(item["low"] for item in raw[:15]))
        self.assertEqual(candles[0]["tick_volume"], sum(item["tick_volume"] for item in raw[:15]))
        self.assertEqual(candles[0]["real_volume"], sum(item["real_volume"] for item in raw[:15]))
        self.assertEqual(candles[0]["spread"], raw[14]["spread"])

    def test_incomplete_latest_m15_bucket_is_excluded(self) -> None:
        normalized = normalize_candles_for_timeframe(m1_candles(37), strategy_timeframe="M15")

        self.assertEqual(len(normalized["candles"]), 2)
        self.assertEqual(normalized["incomplete_strategy_bucket_count"], 1)
        self.assertEqual(normalized["latest_strategy_closed_candle_timestamp"], 900)

    def test_strategy_agents_receive_m15_candles_from_m1_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = self.make_evaluator(tmpdir, m1_candles(25 * 15), [signal("xauusd_paper_v1", "BUY", 0.70)])
            evaluator.evaluate_all_agents()
            trace = evaluator.recent_traces(1)[0]

            self.assertEqual(trace["raw_timeframe"], "M1")
            self.assertEqual(trace["strategy_timeframe"], "M15")
            self.assertTrue(trace["resampled"])
            self.assertEqual(trace["strategy_candle_count"], 25)
            self.assertTrue(all(item["strategy_timeframe"] == "M15" for item in trace["strategy_outputs"]))
            self.assertTrue(all(item["candle_memory_used"] == 25 for item in trace["strategy_outputs"]))

    def test_insufficient_resampled_m15_candles_waits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = self.make_evaluator(tmpdir, m1_candles((24 * 15) + 14), [signal("xauusd_paper_v1", "BUY", 0.99)])
            results = evaluator.evaluate_all_agents()
            trace = evaluator.recent_traces(1)[0]

            self.assertEqual(trace["strategy_candle_count"], 24)
            self.assertTrue(all(result.status == "SKIPPED" for result in results))
            self.assertTrue(all("insufficient_strategy_timeframe_candles" in item["reasons"] for item in trace["strategy_outputs"]))

    def test_highest_confidence_candidate_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = self.make_evaluator(tmpdir, strategy_m15_candles(), [signal("xauusd_paper_v1", "BUY", 0.62), signal("xauusd_paper_v2", "SELL", 0.92)])
            evaluator.evaluate_all_agents()
            trace = evaluator.recent_traces(1)[0]

            self.assertEqual(trace["selected_strategy_id"], "xauusd_paper_v2")
            self.assertEqual(trace["selected_action"], "TRADE_SHORT")

    def test_conflict_too_close_waits(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = self.make_evaluator(tmpdir, strategy_m15_candles(), [])
            outputs = [
                {"strategy_id": "a", "status": "CANDIDATE", "direction": "LONG", "confidence": 0.70},
                {"strategy_id": "b", "status": "CANDIDATE", "direction": "SHORT", "confidence": 0.68},
            ]
            selected, meta = evaluator.select_candidate(outputs, threshold=0.60, conflict_margin=0.05)

            self.assertIsNone(selected)
            self.assertEqual(meta["reason"], "strategy_conflict")

    def test_decision_engine_spread_block_preserves_selected_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evaluator = self.make_evaluator(tmpdir, strategy_m15_candles(), [signal("xauusd_paper_v1", "BUY", 0.90)])
            evaluator.evaluate_all_agents()
            engine = AurixDecisionEngine(
                data_dir=tmpdir,
                config=DecisionEngineConfig(require_event_bus_state=False, require_broker_reconciliation_clean=False, max_spread_points=10),
                snapshot_provider=lambda: {"tick": {"symbol": "XAUUSDm", "spread_points": 999}, "account": {"currency": "GBP"}},
                strategy_agent_store=evaluator.store,
                risk_status_provider=lambda: {"can_trade": True},
            )
            report = engine.evaluate()
            trace = evaluator.store.latest_trace()

            self.assertEqual(report["action"], "BLOCKED_BY_SPREAD")
            self.assertEqual(report["strategy"], "xauusd_paper_v1")
            self.assertEqual(trace["selected_strategy_id"], "xauusd_paper_v1")
            self.assertEqual(trace["block_stage"], "SPREAD")
            self.assertEqual(trace["block_reason"], "spread_above_max")

    def test_paper_trade_record_includes_strategy_cycle_attribution(self) -> None:
        engine = PaperTradingEngine(PaperTradingConfig(), RiskConfig(max_daily_loss_amount=100.0, max_daily_loss_percent=100.0))
        signal_obj = StrategySignal(
            strategy_name="blackcat_cloud_v1",
            strategy_version="1.0.0",
            mode="OBSERVATION_ONLY",
            symbol="XAUUSDm",
            direction="BUY",
            status="PAPER_SIGNAL",
            confidence=0.82,
            strategy_id="blackcat_cloud_v1",
            signal_confidence=0.82,
            signal_reasons=["turned_green", "meter_bull"],
            decision_cycle_id="cycle-123",
            final_gate_result="PAPER_ALLOWED",
        )
        trade, result = engine.create_from_signal(
            signal_obj,
            {"terminal_id": "T1", "tick": {"bid": 100.0, "ask": 100.2, "point": 0.01, "spread_points": 10}, "account": {"balance": 1000.0, "equity": 1000.0}},
            [],
            [],
        )

        self.assertTrue(result["created"])
        self.assertIsNotNone(trade)
        self.assertEqual(trade.strategy_id, "blackcat_cloud_v1")
        self.assertEqual(trade.signal_confidence, 0.82)
        self.assertEqual(trade.signal_reasons, ["turned_green", "meter_bull"])
        self.assertEqual(trade.decision_cycle_id, "cycle-123")
        self.assertEqual(trade.final_gate_result, "PAPER_ALLOWED")

    def test_broker_command_record_includes_strategy_cycle_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DemoBrokerExecutionStore(tmpdir)
            command = store.create_command(
                terminal_id="T1",
                side="BUY",
                symbol="XAUUSDm",
                volume=0.01,
                stop_loss=99.0,
                take_profit=101.0,
                strategy_id="blackcat_cloud_v1",
                signal_id="sig-1",
                signal_confidence=0.91,
                signal_reasons=["turned_green"],
                decision_cycle_id="cycle-456",
                final_gate_result="BROKER_COMMAND_GATE_ALLOWED",
                runtime_session_id="session-1",
                provenance={},
                safety_checks_snapshot={},
                ttl_seconds=60,
                magic_number=1,
            )

            self.assertEqual(command["strategy_id"], "blackcat_cloud_v1")
            self.assertEqual(command["signal_confidence"], 0.91)
            self.assertEqual(command["signal_reasons"], ["turned_green"])
            self.assertEqual(command["decision_cycle_id"], "cycle-456")
            self.assertEqual(command["final_gate_result"], "BROKER_COMMAND_GATE_ALLOWED")


if __name__ == "__main__":
    unittest.main()
