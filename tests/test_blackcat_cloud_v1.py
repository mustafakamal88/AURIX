from __future__ import annotations

import unittest

from aurix_strategy_agents.blackcat_cloud_v1 import BlackCatCloudV1Agent, evaluate_blackcat_cloud_signal
from aurix_strategy_agents.models import StrategyAgentSpec, StrategyEvaluationInput


def flat_candles(count: int = 60, *, price: float = 100.0, volume: float = 100.0) -> list[dict]:
    return [
        {
            "time": index,
            "open": price,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "tick_volume": volume,
            "closed": True,
        }
        for index in range(count)
    ]


def jump_long_candles() -> list[dict]:
    candles = flat_candles()
    candles[-1].update({"open": 100.0, "high": 110.5, "low": 99.5, "close": 110.0})
    return candles


def drop_short_candles() -> list[dict]:
    candles = flat_candles()
    candles[-1].update({"open": 100.0, "high": 100.5, "low": 89.5, "close": 90.0})
    return candles


class BlackCatCloudV1Tests(unittest.TestCase):
    def test_turned_green_meter_bullish_produces_trade_long(self) -> None:
        signal = evaluate_blackcat_cloud_signal(jump_long_candles())

        self.assertEqual(signal.action, "TRADE_LONG")
        self.assertEqual(signal.direction, "LONG")
        self.assertGreater(signal.meter_score, 0.2)
        self.assertTrue(signal.confluence["turned_green"])

    def test_turned_red_meter_bearish_produces_trade_short(self) -> None:
        signal = evaluate_blackcat_cloud_signal(drop_short_candles())

        self.assertEqual(signal.action, "TRADE_SHORT")
        self.assertEqual(signal.direction, "SHORT")
        self.assertLess(signal.meter_score, -0.2)
        self.assertTrue(signal.confluence["turned_red"])

    def test_chop_cloud_produces_wait(self) -> None:
        signal = evaluate_blackcat_cloud_signal(flat_candles())

        self.assertEqual(signal.action, "WAIT")
        self.assertEqual(signal.regime, "CHOP")
        self.assertIn("blackcat_cloud_regime_chop", signal.reasons)

    def test_neutral_meter_produces_wait(self) -> None:
        signal = evaluate_blackcat_cloud_signal(flat_candles())

        self.assertEqual(signal.action, "WAIT")
        self.assertEqual(signal.meter_label, "NEUTRAL")
        self.assertIn("blackcat_meter_neutral", signal.reasons)

    def test_low_confidence_below_threshold_produces_wait(self) -> None:
        signal = evaluate_blackcat_cloud_signal(jump_long_candles(), config={"min_confidence": 0.90})

        self.assertEqual(signal.action, "WAIT")
        self.assertEqual(signal.direction, "NONE")
        self.assertIn("blackcat_confidence_below_threshold", signal.reasons)

    def test_bullish_engulfing_increases_long_confidence(self) -> None:
        base = evaluate_blackcat_cloud_signal(jump_long_candles())
        engulfing = flat_candles()
        engulfing[-2].update({"open": 101.0, "high": 101.5, "low": 98.5, "close": 99.0})
        engulfing[-1].update({"open": 98.0, "high": 111.0, "low": 97.5, "close": 110.0})
        signal = evaluate_blackcat_cloud_signal(engulfing)

        self.assertTrue(signal.confluence["bull_engulf"])
        self.assertGreater(signal.confidence, base.confidence)

    def test_bearish_engulfing_increases_short_confidence(self) -> None:
        base = evaluate_blackcat_cloud_signal(drop_short_candles())
        engulfing = flat_candles()
        engulfing[-2].update({"open": 99.0, "high": 101.5, "low": 98.5, "close": 101.0})
        engulfing[-1].update({"open": 102.0, "high": 102.5, "low": 89.0, "close": 90.0})
        signal = evaluate_blackcat_cloud_signal(engulfing)

        self.assertTrue(signal.confluence["bear_engulf"])
        self.assertGreater(signal.confidence, base.confidence)

    def test_bullish_and_bearish_volume_climax_detected(self) -> None:
        bullish = jump_long_candles()
        bullish[-1]["tick_volume"] = 1000.0
        bullish_signal = evaluate_blackcat_cloud_signal(bullish)

        bearish = drop_short_candles()
        bearish[-1]["tick_volume"] = 1000.0
        bearish_signal = evaluate_blackcat_cloud_signal(bearish)

        self.assertTrue(bullish_signal.confluence["is_climax"])
        self.assertTrue(bullish_signal.confluence["bullish_climax"])
        self.assertTrue(bearish_signal.confluence["is_climax"])
        self.assertTrue(bearish_signal.confluence["bearish_climax"])

    def test_insufficient_candles_returns_wait(self) -> None:
        signal = evaluate_blackcat_cloud_signal(flat_candles(49))

        self.assertEqual(signal.action, "WAIT")
        self.assertIn("insufficient_candles", signal.reasons)

    def test_unfinished_candle_is_not_used(self) -> None:
        candles = jump_long_candles()
        candles.append(
            {
                "time": 60,
                "open": 999.0,
                "high": 1000.0,
                "low": 998.0,
                "close": 999.0,
                "tick_volume": 10000.0,
                "closed": False,
            }
        )
        signal = evaluate_blackcat_cloud_signal(candles)

        self.assertEqual(signal.timestamp, 59)
        self.assertTrue(signal.ignored_unfinished_candle)
        self.assertEqual(signal.action, "TRADE_LONG")

    def test_unmarked_latest_candle_is_not_used(self) -> None:
        candles = jump_long_candles()
        candles.append(
            {
                "time": 60,
                "open": 999.0,
                "high": 1000.0,
                "low": 998.0,
                "close": 999.0,
                "tick_volume": 10000.0,
            }
        )
        signal = evaluate_blackcat_cloud_signal(candles)

        self.assertEqual(signal.timestamp, 59)
        self.assertTrue(signal.ignored_unfinished_candle)
        self.assertEqual(signal.action, "TRADE_LONG")

    def test_agent_returns_aurix_strategy_evaluation_result(self) -> None:
        agent = BlackCatCloudV1Agent(
            StrategyAgentSpec(id="blackcat_cloud_v1", name="BlackCat Cloud V1", source_module="aurix_strategy_agents.blackcat_cloud_v1")
        )
        result = agent.evaluate(StrategyEvaluationInput(agent_id="blackcat_cloud_v1", candles=jump_long_candles()))

        self.assertEqual(result.strategy_name, "blackcat_cloud_v1")
        self.assertEqual(result.status, "SIGNAL")
        self.assertEqual(result.direction, "BUY")
        self.assertIsNone(result.stop_loss_reference)
        self.assertIsNone(result.take_profit_reference)
        self.assertEqual(result.decision_trace["blackcat_signal"]["action"], "TRADE_LONG")


if __name__ == "__main__":
    unittest.main()
