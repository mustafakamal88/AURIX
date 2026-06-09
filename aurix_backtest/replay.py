from __future__ import annotations

from typing import Any, Optional

from .config import BacktestConfig
from .models import BacktestReport, BacktestTrade


class BacktestReplayEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, candles: list[dict[str, Any]]) -> tuple[BacktestReport, list[BacktestTrade]]:
        sorted_candles = sorted(
            [candle for candle in candles if isinstance(candle, dict)],
            key=lambda candle: _sort_key(candle.get("time")),
        )
        warnings: list[str] = []
        trades: list[BacktestTrade] = []
        signals = 0

        if not sorted_candles:
            warnings.append("no candle data")
        if len(sorted_candles) < self.config.min_candles:
            warnings.append("insufficient candles")
        if not self.config.enabled:
            warnings.append("backtest disabled")

        index = max(self.config.min_candles, self.config.lookback_range_candles + 1)
        while self.config.enabled and index < len(sorted_candles):
            signal = self._signal_at(sorted_candles, index)
            if signal is None:
                index += 1
                continue

            signals += 1
            trade, exit_index = self._simulate_trade(sorted_candles, index, signal)
            trades.append(trade)
            index = max(exit_index + 1, index + 1)

        report = self._report(len(sorted_candles), signals, trades, warnings)
        return report, trades

    def _signal_at(self, candles: list[dict[str, Any]], index: int) -> Optional[dict[str, Any]]:
        previous = candles[index - 1]
        current = candles[index]
        lookback = candles[index - self.config.lookback_range_candles - 1 : index - 1]
        if len(lookback) < self.config.lookback_range_candles:
            return None

        if not self._spread_ok(current):
            return None

        range_high = max(_as_float(candle.get("high")) or 0.0 for candle in lookback)
        range_low = min(_as_float(candle.get("low")) or 0.0 for candle in lookback)
        previous_low = _as_float(previous.get("low"))
        previous_high = _as_float(previous.get("high"))
        current_open = _as_float(current.get("open"))
        current_close = _as_float(current.get("close"))
        if None in {previous_low, previous_high, current_open, current_close}:
            return None

        if previous_low < range_low and current_close > range_low and current_close > current_open:
            return {"direction": "BUY", "range_low": range_low, "range_high": range_high, "reasons": ["bullish sweep reclaim"]}
        if previous_high > range_high and current_close < range_high and current_close < current_open:
            return {"direction": "SELL", "range_low": range_low, "range_high": range_high, "reasons": ["bearish sweep reclaim"]}
        return None

    def _simulate_trade(self, candles: list[dict[str, Any]], entry_index: int, signal: dict[str, Any]) -> tuple[BacktestTrade, int]:
        entry_candle = candles[entry_index]
        direction = signal["direction"]
        entry_price = _as_float(entry_candle.get("close")) or 0.0
        point = _as_float(entry_candle.get("point")) or 0.01
        stop_distance = self.config.default_stop_points * point
        take_profit_distance = self.config.default_take_profit_points * point
        if direction == "BUY":
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + take_profit_distance
        else:
            stop_loss = entry_price + stop_distance
            take_profit = entry_price - take_profit_distance

        trade = BacktestTrade(
            symbol=self.config.symbol,
            direction=direction,
            entry_time=entry_candle.get("time"),
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasons=signal["reasons"],
        )

        for index in range(entry_index + 1, len(candles)):
            candle = candles[index]
            high = _as_float(candle.get("high"))
            low = _as_float(candle.get("low"))
            if high is None or low is None:
                continue

            if direction == "BUY":
                sl_hit = low <= stop_loss
                tp_hit = high >= take_profit
                if sl_hit:
                    self._close(trade, "LOSS", candle.get("time"), stop_loss)
                    return trade, index
                if tp_hit:
                    self._close(trade, "WIN", candle.get("time"), take_profit)
                    return trade, index
            else:
                sl_hit = high >= stop_loss
                tp_hit = low <= take_profit
                if sl_hit:
                    self._close(trade, "LOSS", candle.get("time"), stop_loss)
                    return trade, index
                if tp_hit:
                    self._close(trade, "WIN", candle.get("time"), take_profit)
                    return trade, index

        trade.status = "OPEN"
        return trade, len(candles) - 1

    def _close(self, trade: BacktestTrade, status: str, exit_time: Any, exit_price: float) -> None:
        trade.status = status  # type: ignore[assignment]
        trade.exit_time = exit_time
        trade.exit_price = exit_price
        if trade.direction == "BUY":
            pnl_points = exit_price - trade.entry_price
            risk_points = trade.entry_price - trade.stop_loss
        else:
            pnl_points = trade.entry_price - exit_price
            risk_points = trade.stop_loss - trade.entry_price
        trade.pnl_points = round(pnl_points, 6)
        trade.r_multiple = round((pnl_points / risk_points) if risk_points else 0.0, 6)

    def _spread_ok(self, candle: dict[str, Any]) -> bool:
        spread = _as_float(candle.get("spread_points"))
        if spread is None:
            spread = _as_float(candle.get("spread"))
        return spread is None or spread <= self.config.max_spread_points

    def _report(self, candles_used: int, signals: int, trades: list[BacktestTrade], warnings: list[str]) -> BacktestReport:
        wins = [trade for trade in trades if trade.status == "WIN"]
        losses = [trade for trade in trades if trade.status == "LOSS"]
        r_values = [trade.r_multiple for trade in trades if trade.status in {"WIN", "LOSS"}]
        total_positive = sum(value for value in r_values if value > 0)
        total_negative = abs(sum(value for value in r_values if value < 0))
        return BacktestReport(
            symbol=self.config.symbol,
            candles_used=candles_used,
            signals=signals,
            trades=len(trades),
            wins=len(wins),
            losses=len(losses),
            win_rate=round(len(wins) / len(r_values), 6) if r_values else 0.0,
            total_r=round(sum(r_values), 6),
            expectancy_r=round((sum(r_values) / len(r_values)) if r_values else 0.0, 6),
            profit_factor=_profit_factor(total_positive, total_negative, wins),
            max_consecutive_losses=_max_consecutive_losses(trades),
            warnings=warnings,
            safety={
                "backtest_only": True,
                "no_mt5_execution": True,
                "commands_queued": False,
                "external_llm_used": False,
            },
        )


def _max_consecutive_losses(trades: list[BacktestTrade]) -> int:
    best = 0
    current = 0
    for trade in trades:
        if trade.status == "LOSS":
            current += 1
            best = max(best, current)
        elif trade.status == "WIN":
            current = 0
    return best


def _profit_factor(total_positive: float, total_negative: float, wins: list[BacktestTrade]) -> Optional[float]:
    if total_negative == 0:
        return float("inf") if wins else None
    return round(total_positive / total_negative, 6)


def _sort_key(value: Any) -> tuple[int, str]:
    try:
        return (0, f"{int(value):020d}")
    except (TypeError, ValueError):
        return (1, str(value))


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
