from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_research import ParameterSweepEngine, ResearchConfig


def candle(index: int, open_: float, high: float, low: float, close: float) -> dict:
    return {"time": index, "open": open_, "high": high, "low": low, "close": close, "spread": 20}


def base_history() -> list[dict]:
    return [candle(i, 100.0, 101.0, 99.0, 100.0) for i in range(20)]


def sample_candles() -> list[dict]:
    candles = base_history()
    candles.extend(
        [
            candle(20, 100.0, 100.5, 98.5, 99.2),
            candle(21, 99.2, 101.0, 99.1, 100.5),
            candle(22, 100.5, 103.0, 100.4, 102.0),
            candle(23, 100.0, 101.5, 99.5, 100.8),
            candle(24, 100.8, 100.9, 99.0, 99.5),
            candle(25, 99.5, 99.6, 97.0, 98.0),
        ]
    )
    return candles


def main() -> int:
    config_path = PROJECT_ROOT / "config" / "strategy_xauusd_paper_v1.yaml"
    before = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    config = ResearchConfig(
        stop_points_values=[100, 200],
        take_profit_points_values=[200],
        lookback_range_candles_values=[10],
        max_spread_points_values=[100, 350],
        min_trades_required=5,
        max_results=10,
        allow_config_mutation=False,
    )
    engine = ParameterSweepEngine(config)

    empty_run = engine.run([])
    if empty_run.candles_used != 0 or "no candle data" not in empty_run.warnings:
        raise AssertionError(f"no candles should not crash and should warn, got {empty_run}")

    combinations = engine.parameter_combinations()
    if len(combinations) != 4:
        raise AssertionError(f"expected 4 combinations, got {len(combinations)}")

    run = engine.run(sample_candles())
    if not run.results:
        raise AssertionError(f"expected sweep results, got {run}")
    if not any("low sample size" in result.warnings for result in run.results):
        raise AssertionError("expected low sample size warning")
    if run.best_by_total_r is None or run.best_by_expectancy is None or run.best_by_profit_factor is None:
        raise AssertionError(f"expected best result selections, got {run}")
    if run.safety.get("commands_queued") is not False or run.safety.get("no_mt5_execution") is not True:
        raise AssertionError(f"safety flags wrong: {run.safety}")
    if run.safety.get("config_mutated") is not False:
        raise AssertionError(f"config mutation safety flag wrong: {run.safety}")
    after = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    if before != after:
        raise AssertionError("strategy config was mutated")

    print("OK: research self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
