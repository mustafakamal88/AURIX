from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from aurix_common import write_json_atomic

from .base import StrategyAgent
from .indicators import calculate_rsi, calculate_sma, detect_cross_down, detect_cross_up
from .models import StrategyEvaluationInput, StrategyEvaluationResult, StrategyRejectionReason, utc_now_iso


DEFAULT_CONFIG = {
    "enabled": True,
    "symbol": "XAUUSDm",
    "strategy_name": "fast_rsi_first_reversal",
    "strategy_version": "1.0.0",
    "mode": "OBSERVATION_ONLY",
    "timeframe": "M1",
    "closed_bar_only": True,
    "base_lot_reference": 0.01,
    "take_profit_points": 1200,
    "stop_loss_points": 1800,
    "max_spread_points": 250,
    "rsi_period": 14,
    "rsi_sma_period": 9,
    "buy_extreme_level": 30.0,
    "sell_extreme_level": 70.0,
    "balance_low": 45.0,
    "balance_high": 55.0,
    "use_session_filter": False,
    "london_start_hour": 8,
    "london_end_hour": 11,
    "ny_start_hour": 13,
    "ny_end_hour": 16,
    "max_margin_use_percent": 20.0,
    "hmr_margin_multiplier": 3.0,
    "max_slippage_points": 50,
    "allow_signal_generation": True,
    "allow_paper_trade_creation": False,
    "allow_order_request_creation": False,
    "allow_demo_execution": False,
    "allow_live_arming": False,
    "allow_live_execution": False,
    "allow_command_queueing": False,
}


def _reject(code: str, message: str) -> StrategyRejectionReason:
    return StrategyRejectionReason(code=code, message=message)


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class FastRsiFirstReversalAgent(StrategyAgent):
    def __init__(self, spec: Any, config: dict[str, Any], data_dir: str | Path = "data"):
        super().__init__(spec)
        merged = dict(DEFAULT_CONFIG)
        merged.update(config or {})
        self.config = merged
        self.data_dir = Path(data_dir)
        self.state_path = self.data_dir / "strategy_agents" / "fast_rsi_first_reversal_state.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def default_state(self) -> dict[str, Any]:
        return {
            "rsi_was_below_buy_extreme": False,
            "rsi_was_above_sell_extreme": False,
            "last_signal_bar_time": None,
            "last_evaluated_bar_time": None,
            "updated_at": None,
        }

    def read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self.default_state()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return self.default_state()
        state = self.default_state()
        if isinstance(data, dict):
            state.update(data)
        return state

    def write_state(self, state: dict[str, Any]) -> None:
        state["updated_at"] = utc_now_iso()
        write_json_atomic(self.state_path, state)

    def _candles_from_input(self, evaluation_input: StrategyEvaluationInput) -> list[dict[str, Any]]:
        market = evaluation_input.runtime_state.get("market") if isinstance(evaluation_input.runtime_state, dict) else {}
        if isinstance(market, dict):
            for key in ["candle_history", "latest_candles", "candles"]:
                history = market.get(key)
                if isinstance(history, list) and history and all(isinstance(item, dict) for item in history):
                    return history
        candles = [item for item in evaluation_input.candles if isinstance(item, dict)]
        if candles:
            return candles
        latest = (market or {}).get("latest_candle") if isinstance(market, dict) else None
        return [latest] if isinstance(latest, dict) else []

    def _session_allowed(self, bar_time: Any) -> bool:
        if not self.config.get("use_session_filter"):
            return True
        timestamp = _as_int(bar_time)
        hour = datetime.fromtimestamp(timestamp, timezone.utc).hour if timestamp else datetime.now(timezone.utc).hour
        london = _as_int(self.config.get("london_start_hour"), 8) <= hour < _as_int(self.config.get("london_end_hour"), 11)
        ny = _as_int(self.config.get("ny_start_hour"), 13) <= hour < _as_int(self.config.get("ny_end_hour"), 16)
        return bool(london or ny)

    def _market_refs(self, evaluation_input: StrategyEvaluationInput, candle: dict[str, Any]) -> dict[str, Any]:
        market = evaluation_input.runtime_state.get("market") if isinstance(evaluation_input.runtime_state, dict) else {}
        tick = (market or {}).get("latest_tick") if isinstance(market, dict) else {}
        tick = tick if isinstance(tick, dict) else {}
        return {
            "bid": _as_float(tick.get("bid"), _as_float(candle.get("close"))),
            "ask": _as_float(tick.get("ask"), _as_float(candle.get("close"))),
            "point": _as_float(tick.get("point"), 0.01) or 0.01,
            "spread_points": _as_float(tick.get("spread_points"), _as_float(candle.get("spread"))),
        }

    def _account_refs(self, evaluation_input: StrategyEvaluationInput) -> dict[str, Any]:
        account = evaluation_input.runtime_state.get("account") if isinstance(evaluation_input.runtime_state, dict) else {}
        return account if isinstance(account, dict) else {}

    def _hmr(self, account: dict[str, Any]) -> tuple[bool, bool, list[str], Optional[float]]:
        equity = _as_float(account.get("equity"))
        margin = _as_float(account.get("margin"), 0.0)
        free_margin = _as_float(account.get("margin_free"), _as_float(account.get("free_margin")))
        if equity is None or free_margin is None:
            return False, True, ["hmr_margin_data_unavailable"], None
        projected_margin = (margin or 0.0) * float(self.config.get("hmr_margin_multiplier") or 1.0)
        margin_use_percent = (projected_margin / equity * 100.0) if equity else None
        if margin_use_percent is None:
            return True, True, [], None
        return True, margin_use_percent <= float(self.config.get("max_margin_use_percent") or 20.0), [], margin_use_percent

    def _base_result(self, status: str, trace: dict[str, Any], rejection_reasons: list[StrategyRejectionReason], warnings: list[str]) -> StrategyEvaluationResult:
        return StrategyEvaluationResult(
            agent_id=self.spec.id,
            strategy_name=str(self.config.get("strategy_name") or "fast_rsi_first_reversal"),
            strategy_version=str(self.config.get("strategy_version") or "1.0.0"),
            symbol=str(self.config.get("symbol") or self.spec.symbol),
            mode=str(self.config.get("mode") or self.spec.mode),
            status=status,  # type: ignore[arg-type]
            confidence=0.0,
            setup_reason=None,
            decision_trace=trace,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
        )

    def evaluate(self, evaluation_input: StrategyEvaluationInput) -> StrategyEvaluationResult:
        state = self.read_state()
        before_below = bool(state.get("rsi_was_below_buy_extreme"))
        before_above = bool(state.get("rsi_was_above_sell_extreme"))
        candles = self._candles_from_input(evaluation_input)
        rsi_period = _as_int(self.config.get("rsi_period"), 14)
        sma_period = _as_int(self.config.get("rsi_sma_period"), 9)
        required = rsi_period + sma_period + 2
        warnings: list[str] = []
        rejection_reasons: list[StrategyRejectionReason] = []

        empty_trace = {
            "trace_version": "1.0",
            "strategy": "fast_rsi_first_reversal",
            "strategy_version": str(self.config.get("strategy_version") or "1.0.0"),
            "generated_at": utc_now_iso(),
            "symbol": str(self.config.get("symbol") or self.spec.symbol),
            "timeframe": str(self.config.get("timeframe") or "M1"),
            "closed_bar_only": bool(self.config.get("closed_bar_only", True)),
            "rule_checks": {"enough_candles": len(candles) >= required},
        }
        if len(candles) < required:
            rejection_reasons.append(_reject("insufficient_m1_candles_for_rsi", f"Need at least {required} candles, got {len(candles)}."))
            return self._base_result("SKIPPED", empty_trace, rejection_reasons, warnings)

        evaluated = candles[-1]
        previous = candles[-2]
        closes = [_as_float(candle.get("close")) for candle in candles]
        if any(close is None for close in closes):
            rejection_reasons.append(_reject("invalid_candle_close", "At least one candle close is missing or invalid."))
            return self._base_result("SKIPPED", empty_trace, rejection_reasons, warnings)
        numeric_closes = [float(close) for close in closes if close is not None]
        rsi_values = calculate_rsi(numeric_closes, rsi_period)
        rsi_sma_values = calculate_sma(rsi_values, sma_period)
        rsi_previous = rsi_values[-2]
        rsi_current = rsi_values[-1]
        rsi_sma_previous = rsi_sma_values[-2]
        rsi_sma_current = rsi_sma_values[-1]
        if rsi_previous is None or rsi_current is None or rsi_sma_previous is None or rsi_sma_current is None:
            rejection_reasons.append(_reject("insufficient_m1_candles_for_rsi", "RSI or RSI SMA is unavailable for the evaluated bar."))
            return self._base_result("SKIPPED", empty_trace, rejection_reasons, warnings)

        refs = self._market_refs(evaluation_input, evaluated)
        account = self._account_refs(evaluation_input)
        hmr_available, hmr_ok, hmr_warnings, margin_use_percent = self._hmr(account)
        warnings.extend(hmr_warnings)
        spread_points = refs.get("spread_points")
        max_spread_points = float(self.config.get("max_spread_points") or 250.0)
        spread_ok = spread_points is not None and float(spread_points) <= max_spread_points
        symbol_matched = str(evaluated.get("symbol") or self.config.get("symbol")) == str(self.config.get("symbol"))
        session_allowed = self._session_allowed(evaluated.get("time"))
        in_balance_zone = float(self.config.get("balance_low")) <= float(rsi_current) <= float(self.config.get("balance_high"))
        one_signal_per_bar_ok = str(state.get("last_signal_bar_time")) != str(evaluated.get("time"))
        cross_up = detect_cross_up(rsi_previous, rsi_sma_previous, rsi_current, rsi_sma_current)
        cross_down = detect_cross_down(rsi_previous, rsi_sma_previous, rsi_current, rsi_sma_current)

        after_below = before_below
        after_above = before_above
        buy_extreme_seen = before_below
        sell_extreme_seen = before_above

        if in_balance_zone:
            after_below = False
            after_above = False
        else:
            if float(rsi_current) < float(self.config.get("buy_extreme_level")):
                after_below = True
                buy_extreme_seen = True
            if float(rsi_current) > float(self.config.get("sell_extreme_level")):
                after_above = True
                sell_extreme_seen = True

        buy_valid = (
            bool(self.config.get("allow_signal_generation", True))
            and symbol_matched
            and spread_ok
            and session_allowed
            and one_signal_per_bar_ok
            and buy_extreme_seen
            and cross_up
            and float(rsi_current) < float(self.config.get("balance_low"))
        )
        sell_valid = (
            bool(self.config.get("allow_signal_generation", True))
            and symbol_matched
            and spread_ok
            and session_allowed
            and one_signal_per_bar_ok
            and sell_extreme_seen
            and cross_down
            and float(rsi_current) > float(self.config.get("balance_high"))
        )

        trace = {
            **empty_trace,
            "evaluated_bar_time": evaluated.get("time"),
            "previous_bar_time": previous.get("time"),
            "point": refs.get("point"),
            "bid": refs.get("bid"),
            "ask": refs.get("ask"),
            "spread_points": spread_points,
            "max_spread_points": max_spread_points,
            "account_currency": account.get("currency"),
            "balance": account.get("balance"),
            "equity": account.get("equity"),
            "free_margin": account.get("margin_free") or account.get("free_margin"),
            "margin_use_percent": margin_use_percent,
            "rsi_period": rsi_period,
            "rsi_sma_period": sma_period,
            "rsi_previous": rsi_previous,
            "rsi_current": rsi_current,
            "rsi_sma_previous": rsi_sma_previous,
            "rsi_sma_current": rsi_sma_current,
            "rsi_was_below_buy_extreme_before": before_below,
            "rsi_was_above_sell_extreme_before": before_above,
            "rsi_was_below_buy_extreme_after": False if (buy_valid or sell_valid) else after_below,
            "rsi_was_above_sell_extreme_after": False if (buy_valid or sell_valid) else after_above,
            "rule_checks": {
                "symbol_matched": symbol_matched,
                "spread_ok": spread_ok,
                "session_allowed": session_allowed,
                "enough_candles": True,
                "balance_zone_reset": in_balance_zone,
                "one_signal_per_bar_ok": one_signal_per_bar_ok,
                "buy_extreme_seen": buy_extreme_seen,
                "sell_extreme_seen": sell_extreme_seen,
                "cross_up": cross_up,
                "cross_down": cross_down,
                "buy_valid": buy_valid,
                "sell_valid": sell_valid,
                "hmr_check_available": hmr_available,
                "hmr_ok": hmr_ok,
            },
        }

        state["last_evaluated_bar_time"] = evaluated.get("time")

        if in_balance_zone:
            state["rsi_was_below_buy_extreme"] = False
            state["rsi_was_above_sell_extreme"] = False
            self.write_state(state)
            return self._base_result("NO_SIGNAL", trace, [_reject("balance_zone_reset", "RSI entered the balance zone; extreme-state flags reset.")], warnings)
        if not symbol_matched:
            rejection_reasons.append(_reject("symbol_mismatch", "Evaluated symbol does not match Fast RSI config symbol."))
        if not spread_ok:
            rejection_reasons.append(_reject("spread_above_max", f"Spread {spread_points} exceeds max {max_spread_points}."))
        if not session_allowed:
            rejection_reasons.append(_reject("session_filter_blocked", "Session filter blocked this evaluation."))
        if not one_signal_per_bar_ok:
            rejection_reasons.append(_reject("one_signal_per_bar", "A signal was already emitted for this bar."))

        if buy_valid or sell_valid:
            direction = "BUY" if buy_valid else "SELL"
            point = float(refs.get("point") or 0.01)
            entry = float(refs.get("ask") if direction == "BUY" else refs.get("bid"))
            sl_points = float(self.config.get("stop_loss_points") or 1800)
            tp_points = float(self.config.get("take_profit_points") or 1200)
            stop = entry - sl_points * point if direction == "BUY" else entry + sl_points * point
            take = entry + tp_points * point if direction == "BUY" else entry - tp_points * point
            state["rsi_was_below_buy_extreme"] = False
            state["rsi_was_above_sell_extreme"] = False
            state["last_signal_bar_time"] = evaluated.get("time")
            self.write_state(state)
            reason = (
                "RSI first dropped below buy extreme, then crossed above RSI SMA while below balance zone"
                if direction == "BUY"
                else "RSI first rose above sell extreme, then crossed below RSI SMA while above balance zone"
            )
            return StrategyEvaluationResult(
                agent_id=self.spec.id,
                strategy_name=str(self.config.get("strategy_name")),
                strategy_version=str(self.config.get("strategy_version")),
                symbol=str(self.config.get("symbol")),
                mode=str(self.config.get("mode")),
                status="SIGNAL",
                direction=direction,
                confidence=0.68,
                entry_reference=entry,
                stop_loss_reference=stop,
                take_profit_reference=take,
                setup_reason=reason,
                decision_trace=trace,
                rejection_reasons=[],
                warnings=warnings,
            )

        state["rsi_was_below_buy_extreme"] = after_below
        state["rsi_was_above_sell_extreme"] = after_above
        self.write_state(state)
        if not rejection_reasons:
            rejection_reasons.append(_reject("no_fast_rsi_first_reversal_setup", "No Fast RSI first-reversal setup on the evaluated closed bar."))
        return self._base_result("SKIPPED" if rejection_reasons and rejection_reasons[0].code in {"spread_above_max", "session_filter_blocked", "one_signal_per_bar", "symbol_mismatch"} else "NO_SIGNAL", trace, rejection_reasons, warnings)
