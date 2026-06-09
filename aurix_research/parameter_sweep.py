from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any, Iterable, Optional

from aurix_backtest import BacktestConfig, BacktestReplayEngine

from .config import ResearchConfig
from .models import ResearchRun, SweepResult


SAFETY = {
    "research_only": True,
    "no_mt5_execution": True,
    "commands_queued": False,
    "config_mutated": False,
    "external_llm_used": False,
}


class ParameterSweepEngine:
    def __init__(self, config: ResearchConfig):
        self.config = config

    def run(self, candles: list[dict[str, Any]]) -> ResearchRun:
        sorted_candles = [candle for candle in candles if isinstance(candle, dict)]
        warnings: list[str] = []
        if not sorted_candles:
            warnings.append("no candle data")
        if not self.config.enabled:
            warnings.append("research disabled")

        combinations = self.parameter_combinations()
        results: list[SweepResult] = []
        if self.config.enabled:
            for params in combinations:
                result = self._run_variant(sorted_candles, params)
                results.append(result)

        results = sorted(
            results,
            key=lambda result: (
                result.total_r,
                result.expectancy_r,
                _profit_factor_score(result.profit_factor),
                result.trades,
            ),
            reverse=True,
        )[: max(self.config.max_results, 0)]

        return ResearchRun(
            symbol=self.config.symbol,
            candles_used=len(sorted_candles),
            total_variants=len(combinations),
            results=results,
            best_by_total_r=_best(results, "total_r"),
            best_by_expectancy=_best(results, "expectancy_r"),
            best_by_profit_factor=_best_profit_factor(results),
            warnings=warnings,
            safety=SAFETY.copy(),
        )

    def parameter_combinations(self) -> list[dict[str, Any]]:
        return [
            {
                "stop_points": stop_points,
                "take_profit_points": take_profit_points,
                "lookback_range_candles": lookback_range_candles,
                "max_spread_points": max_spread_points,
            }
            for stop_points, take_profit_points, lookback_range_candles, max_spread_points in product(
                self.config.stop_points_values,
                self.config.take_profit_points_values,
                self.config.lookback_range_candles_values,
                self.config.max_spread_points_values,
            )
        ]

    def _run_variant(self, candles: list[dict[str, Any]], params: dict[str, Any]) -> SweepResult:
        backtest_config = BacktestConfig(
            enabled=self.config.enabled,
            symbol=self.config.symbol,
            source_candles_file=self.config.source_candles_file,
            default_stop_points=float(params["stop_points"]),
            default_take_profit_points=float(params["take_profit_points"]),
            lookback_range_candles=int(params["lookback_range_candles"]),
            max_spread_points=float(params["max_spread_points"]),
        )
        report, _ = BacktestReplayEngine(backtest_config).run(candles)
        warnings = list(report.warnings)
        if report.trades < self.config.min_trades_required:
            warnings.append("low sample size")
        return SweepResult(
            params=params,
            candles_used=report.candles_used,
            trades=report.trades,
            wins=report.wins,
            losses=report.losses,
            win_rate=report.win_rate,
            total_r=report.total_r,
            expectancy_r=report.expectancy_r,
            profit_factor=report.profit_factor,
            max_consecutive_losses=report.max_consecutive_losses,
            warnings=warnings,
        )


def load_recorded_candles(path: str | Path) -> list[dict[str, Any]]:
    import json

    source = Path(path)
    if not source.exists():
        return []
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _best(results: Iterable[SweepResult], field: str) -> Optional[SweepResult]:
    values = list(results)
    if not values:
        return None
    return max(values, key=lambda result: (float(getattr(result, field) or 0.0), result.trades))


def _best_profit_factor(results: Iterable[SweepResult]) -> Optional[SweepResult]:
    values = list(results)
    if not values:
        return None
    return max(values, key=lambda result: (_profit_factor_score(result.profit_factor), result.trades, result.total_r))


def _profit_factor_score(value: Optional[float]) -> float:
    if value is None:
        return -1.0
    return float(value)
