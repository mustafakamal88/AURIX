from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_backtest import BacktestConfig, BacktestReplayEngine


def candle(index: int, open_: float, high: float, low: float, close: float) -> dict:
    return {"time": index, "open": open_, "high": high, "low": low, "close": close, "spread": 20}


def base_history() -> list[dict]:
    return [candle(i, 100.0, 101.0, 99.0, 100.0) for i in range(20)]


def run(candles: list[dict]):
    engine = BacktestReplayEngine(
        BacktestConfig(
            min_candles=20,
            lookback_range_candles=10,
            default_stop_points=100,
            default_take_profit_points=200,
        )
    )
    return engine.run(candles)


def assert_trade(candles: list[dict], status: str, direction: str, label: str) -> None:
    report, trades = run(candles)
    if not trades:
        raise AssertionError(f"{label}: expected trade, got none report={report}")
    trade = trades[0]
    if trade.status != status or trade.direction != direction:
        raise AssertionError(f"{label}: expected {direction} {status}, got {trade.direction} {trade.status}")


def buy_setup(exit_candle: dict) -> list[dict]:
    candles = base_history()
    candles.append(candle(20, 100.0, 100.5, 98.5, 99.2))
    candles.append(candle(21, 99.2, 101.0, 99.1, 100.5))
    candles.append(exit_candle)
    return candles


def sell_setup(exit_candle: dict) -> list[dict]:
    candles = base_history()
    candles.append(candle(20, 100.0, 101.5, 99.5, 100.8))
    candles.append(candle(21, 100.8, 100.9, 99.0, 99.5))
    candles.append(exit_candle)
    return candles


def main() -> int:
    report, trades = run([])
    if trades or "no candle data" not in report.warnings:
        raise AssertionError(f"no data should warn and not crash, got {report}")

    report, trades = run(base_history()[:5])
    if trades or "insufficient candles" not in report.warnings:
        raise AssertionError(f"insufficient data should warn, got {report}")

    assert_trade(buy_setup(candle(22, 100.5, 103.0, 100.4, 102.0)), "WIN", "BUY", "buy TP")
    assert_trade(buy_setup(candle(22, 100.5, 101.0, 99.0, 99.5)), "LOSS", "BUY", "buy SL")
    assert_trade(sell_setup(candle(22, 99.5, 99.6, 97.0, 98.0)), "WIN", "SELL", "sell TP")
    assert_trade(sell_setup(candle(22, 99.5, 101.0, 99.0, 100.5)), "LOSS", "SELL", "sell SL")
    assert_trade(buy_setup(candle(22, 100.5, 103.0, 99.0, 101.0)), "LOSS", "BUY", "same candle conservative")

    report, _ = run(buy_setup(candle(22, 100.5, 103.0, 100.4, 102.0)))
    if report.safety.get("commands_queued") is not False or report.safety.get("no_mt5_execution") is not True:
        raise AssertionError(f"safety flags wrong: {report.safety}")

    print("OK: backtest self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
