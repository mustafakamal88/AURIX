from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .base import StrategyAgent
from .indicators import calculate_ema, calculate_rsi, calculate_sma
from .models import StrategyEvaluationInput, StrategyEvaluationResult, StrategyRejectionReason, utc_now_iso


DEFAULT_CONFIG = {
    "enabled": True,
    "symbol": "XAUUSDm",
    "strategy_name": "blackcat_cloud_v1",
    "strategy_version": "1.0.0",
    "mode": "OBSERVATION_ONLY",
    "timeframe": "M15",
    "closed_bar_only": True,
    "ema_fast": 8,
    "ema_slow": 21,
    "chop_threshold_pct": 0.2,
    "score_speed": 0.3,
    "volume_ma_len": 20,
    "climax_mult": 3.0,
    "rsi_len": 14,
    "meter_ema_len": 20,
    "meter_smoothing": 3,
    "divergence_pivot_left": 3,
    "divergence_pivot_right": 3,
    "min_bars_required": 50,
    "min_confidence": 0.60,
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


def _candle_time(candle: dict[str, Any]) -> Any:
    return candle.get("time") or candle.get("timestamp") or candle.get("datetime")


def _volume(candle: dict[str, Any]) -> Optional[float]:
    return _as_float(candle.get("real_volume"), _as_float(candle.get("volume"), _as_float(candle.get("tick_volume"))))


def _is_unfinished(candle: dict[str, Any]) -> bool:
    for key in ("closed", "is_closed", "complete", "is_complete"):
        if key in candle:
            return not bool(candle.get(key))
    return False


def _has_closed_marker(candle: dict[str, Any]) -> bool:
    return any(key in candle for key in ("closed", "is_closed", "complete", "is_complete"))


def _closed_candles(candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if candles and (_is_unfinished(candles[-1]) or not _has_closed_marker(candles[-1])):
        return candles[:-1]
    return candles


def _pivot_low(values: list[Optional[float]], index: int, left: int, right: int) -> bool:
    value = values[index] if 0 <= index < len(values) else None
    if value is None or index - left < 0 or index + right >= len(values):
        return False
    return all(other is not None and float(value) <= float(other) for other in values[index - left : index]) and all(
        other is not None and float(value) <= float(other) for other in values[index + 1 : index + right + 1]
    )


def _pivot_high(values: list[Optional[float]], index: int, left: int, right: int) -> bool:
    value = values[index] if 0 <= index < len(values) else None
    if value is None or index - left < 0 or index + right >= len(values):
        return False
    return all(other is not None and float(value) >= float(other) for other in values[index - left : index]) and all(
        other is not None and float(value) >= float(other) for other in values[index + 1 : index + right + 1]
    )


def _meter_label(score: Optional[float]) -> str:
    if score is None:
        return "NEUTRAL"
    if score > 0.6:
        return "STRONG_BULL"
    if score > 0.2:
        return "BULL"
    if score >= -0.2:
        return "NEUTRAL"
    if score > -0.6:
        return "BEAR"
    return "STRONG_BEAR"


@dataclass(frozen=True)
class BlackCatSignal:
    strategy_id: str
    symbol: str
    timeframe: str
    timestamp: Any
    action: str
    direction: str
    confidence: float
    regime: str
    cloud_score: float
    meter_score: float
    meter_label: str
    reasons: list[str]
    confluence: dict[str, Any]
    closed_candle_count: int
    ignored_unfinished_candle: bool

    def model_dump(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp,
            "action": self.action,
            "direction": self.direction,
            "confidence": self.confidence,
            "regime": self.regime,
            "cloud_score": self.cloud_score,
            "meter_score": self.meter_score,
            "meter_label": self.meter_label,
            "reasons": self.reasons,
            "confluence": self.confluence,
            "closed_candle_count": self.closed_candle_count,
            "ignored_unfinished_candle": self.ignored_unfinished_candle,
        }


def evaluate_blackcat_cloud_signal(candles: list[dict[str, Any]], *, symbol: str = "XAUUSDm", timeframe: str = "M15", config: dict[str, Any] | None = None) -> BlackCatSignal:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    original_count = len(candles)
    candles = _closed_candles([item for item in candles if isinstance(item, dict)])
    ignored_unfinished = len(candles) != original_count
    required = max(_as_int(cfg.get("min_bars_required"), 50), 50)
    if len(candles) < required:
        return BlackCatSignal(
            strategy_id="blackcat_cloud_v1",
            symbol=symbol,
            timeframe=timeframe,
            timestamp=_candle_time(candles[-1]) if candles else None,
            action="WAIT",
            direction="NONE",
            confidence=0.0,
            regime="CHOP",
            cloud_score=0.0,
            meter_score=0.0,
            meter_label="NEUTRAL",
            reasons=["insufficient_candles"],
            confluence={},
            closed_candle_count=len(candles),
            ignored_unfinished_candle=ignored_unfinished,
        )

    opens = [_as_float(item.get("open")) for item in candles]
    highs = [_as_float(item.get("high")) for item in candles]
    lows = [_as_float(item.get("low")) for item in candles]
    closes = [_as_float(item.get("close")) for item in candles]
    volumes = [_volume(item) for item in candles]
    if any(value is None for row in (opens, highs, lows, closes, volumes) for value in row):
        return BlackCatSignal(
            strategy_id="blackcat_cloud_v1",
            symbol=symbol,
            timeframe=timeframe,
            timestamp=_candle_time(candles[-1]),
            action="WAIT",
            direction="NONE",
            confidence=0.0,
            regime="CHOP",
            cloud_score=0.0,
            meter_score=0.0,
            meter_label="NEUTRAL",
            reasons=["invalid_candle_data"],
            confluence={},
            closed_candle_count=len(candles),
            ignored_unfinished_candle=ignored_unfinished,
        )

    numeric_opens = [float(value) for value in opens if value is not None]
    numeric_highs = [float(value) for value in highs if value is not None]
    numeric_lows = [float(value) for value in lows if value is not None]
    numeric_closes = [float(value) for value in closes if value is not None]
    numeric_volumes = [float(value) for value in volumes if value is not None]

    ema_fast = _as_int(cfg.get("ema_fast"), 8)
    ema_slow = _as_int(cfg.get("ema_slow"), 21)
    fast = calculate_ema(numeric_closes, ema_fast)
    slow = calculate_ema(numeric_closes, ema_slow)
    meter_ema = calculate_ema(numeric_closes, _as_int(cfg.get("meter_ema_len"), 20))
    rsi_values = calculate_rsi(numeric_closes, _as_int(cfg.get("rsi_len"), 14))
    vol_ma = calculate_sma([float(value) for value in numeric_volumes], _as_int(cfg.get("volume_ma_len"), 20))

    target_scores: list[float] = []
    green_flags: list[bool] = []
    red_flags: list[bool] = []
    avg_slopes: list[Optional[float]] = []
    score = 0.0
    threshold = float(cfg.get("chop_threshold_pct") or 0.2)
    speed = float(cfg.get("score_speed") or 0.3)
    for index, close in enumerate(numeric_closes):
        fast_value = fast[index]
        slow_value = slow[index]
        if index < 5 or fast_value is None or slow_value is None or fast[index - 5] in (None, 0) or slow[index - 5] in (None, 0):
            green_flags.append(False)
            red_flags.append(False)
            avg_slopes.append(None)
            target = 0.0
        else:
            fast_slope = ((float(fast_value) - float(fast[index - 5])) / float(fast[index - 5])) * 100.0
            slow_slope = ((float(slow_value) - float(slow[index - 5])) / float(slow[index - 5])) * 100.0
            avg_slope = (fast_slope + slow_slope) / 2.0
            above_cloud = close > float(fast_value) and close > float(slow_value) and float(fast_value) > float(slow_value)
            below_cloud = close < float(fast_value) and close < float(slow_value) and float(fast_value) < float(slow_value)
            is_green = above_cloud and avg_slope > threshold
            is_red = below_cloud and avg_slope < -threshold
            green_flags.append(is_green)
            red_flags.append(is_red)
            avg_slopes.append(avg_slope)
            target = 1.0 if is_green else -1.0 if is_red else 0.0
        score = score + ((target - score) * speed)
        target_scores.append(score)

    meter_raw_scores: list[Optional[float]] = []
    for index, close in enumerate(numeric_closes):
        ema_value = meter_ema[index]
        ema_prev = meter_ema[index - 3] if index >= 3 else None
        if ema_value in (None, 0) or ema_prev in (None, 0):
            meter_raw_scores.append(None)
            continue
        m_slope = ((float(ema_value) - float(ema_prev)) / float(ema_prev)) * 100.0
        m_vs_ema = ((close - float(ema_value)) / float(ema_value)) * 100.0
        m_raw = (m_slope * 3.0) + (m_vs_ema * 2.0)
        meter_raw_scores.append(m_raw / (1.0 + abs(m_raw)))
    meter_scores = calculate_ema(meter_raw_scores, _as_int(cfg.get("meter_smoothing"), 3))

    index = len(candles) - 1
    previous_index = index - 1
    is_green = green_flags[index]
    is_red = red_flags[index]
    turned_green = is_green and not green_flags[previous_index]
    turned_red = is_red and not red_flags[previous_index]
    latest_meter_score = float(meter_scores[index] or 0.0)
    label = _meter_label(latest_meter_score)
    latest_vol_ma = vol_ma[index]
    is_climax = bool(latest_vol_ma is not None and numeric_volumes[index] >= float(latest_vol_ma) * float(cfg.get("climax_mult") or 3.0))
    bullish_climax = is_climax and numeric_closes[index] >= numeric_opens[index]
    bearish_climax = is_climax and numeric_closes[index] < numeric_opens[index]
    bull_engulf = (
        numeric_closes[index] > numeric_opens[index]
        and numeric_closes[index] > numeric_opens[previous_index]
        and numeric_opens[index] < numeric_closes[previous_index]
        and numeric_opens[previous_index] > numeric_closes[previous_index]
    )
    bear_engulf = (
        numeric_closes[index] < numeric_opens[index]
        and numeric_closes[index] < numeric_opens[previous_index]
        and numeric_opens[index] > numeric_closes[previous_index]
        and numeric_opens[previous_index] < numeric_closes[previous_index]
    )

    pivot_left = _as_int(cfg.get("divergence_pivot_left"), 3)
    pivot_right = _as_int(cfg.get("divergence_pivot_right"), 3)
    pivot_index = index - 3
    compare_index = index - 6
    bull_div = (
        compare_index >= 0
        and _pivot_low(rsi_values, pivot_index, pivot_left, pivot_right)
        and _pivot_low([float(value) for value in numeric_lows], pivot_index, pivot_left, pivot_right)
        and numeric_lows[pivot_index] < numeric_lows[compare_index]
        and rsi_values[pivot_index] is not None
        and rsi_values[compare_index] is not None
        and float(rsi_values[pivot_index]) > float(rsi_values[compare_index])
    )
    bear_div = (
        compare_index >= 0
        and _pivot_high(rsi_values, pivot_index, pivot_left, pivot_right)
        and _pivot_high([float(value) for value in numeric_highs], pivot_index, pivot_left, pivot_right)
        and numeric_highs[pivot_index] > numeric_highs[compare_index]
        and rsi_values[pivot_index] is not None
        and rsi_values[compare_index] is not None
        and float(rsi_values[pivot_index]) < float(rsi_values[compare_index])
    )

    regime = "BULLISH" if is_green else "BEARISH" if is_red else "CHOP"
    long_candidate = bool(turned_green and latest_meter_score > 0.2)
    short_candidate = bool(turned_red and latest_meter_score < -0.2)
    reasons: list[str] = []
    action = "WAIT"
    direction = "NONE"
    confidence = 0.0

    if long_candidate:
        action = "TRADE_LONG"
        direction = "LONG"
        confidence += 0.45
        if latest_meter_score > 0.2:
            confidence += 0.20
        if latest_meter_score > 0.6:
            confidence += 0.10
        if bull_engulf:
            confidence += 0.10
        if bull_div:
            confidence += 0.10
        if bullish_climax:
            confidence += 0.05
        if bear_engulf or bear_div or bearish_climax:
            confidence -= 0.15
            reasons.append("bearish_confluence_conflict")
    elif short_candidate:
        action = "TRADE_SHORT"
        direction = "SHORT"
        confidence += 0.45
        if latest_meter_score < -0.2:
            confidence += 0.20
        if latest_meter_score < -0.6:
            confidence += 0.10
        if bear_engulf:
            confidence += 0.10
        if bear_div:
            confidence += 0.10
        if bearish_climax:
            confidence += 0.05
        if bull_engulf or bull_div or bullish_climax:
            confidence -= 0.15
            reasons.append("bullish_confluence_conflict")

    confidence = max(0.0, min(confidence, 0.95))
    if regime == "CHOP":
        action = "WAIT"
        direction = "NONE"
        reasons.append("blackcat_cloud_regime_chop")
    if label == "NEUTRAL":
        action = "WAIT"
        direction = "NONE"
        reasons.append("blackcat_meter_neutral")
    if action != "WAIT" and confidence < float(cfg.get("min_confidence") or 0.60):
        action = "WAIT"
        direction = "NONE"
        reasons.append("blackcat_confidence_below_threshold")
    if action == "TRADE_LONG":
        reasons.append("blackcat_turned_green_meter_bullish")
    elif action == "TRADE_SHORT":
        reasons.append("blackcat_turned_red_meter_bearish")
    elif not reasons:
        reasons.append("blackcat_no_trade_setup")

    confluence = {
        "turned_green": turned_green,
        "turned_red": turned_red,
        "is_green": is_green,
        "is_red": is_red,
        "bull_engulf": bull_engulf,
        "bear_engulf": bear_engulf,
        "bull_div": bull_div,
        "bear_div": bear_div,
        "is_climax": is_climax,
        "bullish_climax": bullish_climax,
        "bearish_climax": bearish_climax,
        "avg_slope": avg_slopes[index],
        "fast_ema": fast[index],
        "slow_ema": slow[index],
    }
    return BlackCatSignal(
        strategy_id="blackcat_cloud_v1",
        symbol=symbol,
        timeframe=timeframe,
        timestamp=_candle_time(candles[-1]),
        action=action,
        direction=direction,
        confidence=round(confidence, 6),
        regime=regime,
        cloud_score=round(float(target_scores[index]), 6),
        meter_score=round(latest_meter_score, 6),
        meter_label=label,
        reasons=list(dict.fromkeys(reasons)),
        confluence=confluence,
        closed_candle_count=len(candles),
        ignored_unfinished_candle=ignored_unfinished,
    )


class BlackCatCloudV1Agent(StrategyAgent):
    def __init__(self, spec: Any, config: dict[str, Any] | None = None):
        super().__init__(spec)
        merged = dict(DEFAULT_CONFIG)
        merged.update(config or {})
        self.config = merged

    def _candles_from_input(self, evaluation_input: StrategyEvaluationInput) -> list[dict[str, Any]]:
        market = evaluation_input.runtime_state.get("market") if isinstance(evaluation_input.runtime_state, dict) else {}
        if isinstance(market, dict):
            for key in ("candle_history", "latest_candles", "candles"):
                history = market.get(key)
                if isinstance(history, list) and history and all(isinstance(item, dict) for item in history):
                    return history
        candles = [item for item in evaluation_input.candles if isinstance(item, dict)]
        if candles:
            return candles
        latest = (market or {}).get("latest_candle") if isinstance(market, dict) else None
        return [latest] if isinstance(latest, dict) else []

    def _base_result(self, signal: BlackCatSignal, status: str, rejection_reasons: list[StrategyRejectionReason]) -> StrategyEvaluationResult:
        trace = {
            "trace_version": "1.0",
            "strategy": "blackcat_cloud_v1",
            "strategy_version": str(self.config.get("strategy_version") or "1.0.0"),
            "generated_at": utc_now_iso(),
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "closed_bar_only": True,
            "blackcat_signal": signal.model_dump(),
            "rule_checks": {
                "enough_candles": signal.closed_candle_count >= int(self.config.get("min_bars_required") or 50),
                "ignored_unfinished_candle": signal.ignored_unfinished_candle,
                "confidence_threshold": self.config.get("min_confidence"),
            },
        }
        direction = "BUY" if signal.action == "TRADE_LONG" else "SELL" if signal.action == "TRADE_SHORT" else None
        return StrategyEvaluationResult(
            agent_id=self.spec.id,
            strategy_name="blackcat_cloud_v1",
            strategy_version=str(self.config.get("strategy_version") or "1.0.0"),
            symbol=str(self.config.get("symbol") or self.spec.symbol),
            mode=str(self.config.get("mode") or self.spec.mode),
            status=status,  # type: ignore[arg-type]
            direction=direction,
            confidence=signal.confidence,
            setup_reason="; ".join(signal.reasons) if signal.reasons else None,
            decision_trace=trace,
            rejection_reasons=rejection_reasons,
            warnings=[],
        )

    def evaluate(self, evaluation_input: StrategyEvaluationInput) -> StrategyEvaluationResult:
        signal = evaluate_blackcat_cloud_signal(
            self._candles_from_input(evaluation_input),
            symbol=str(self.config.get("symbol") or evaluation_input.symbol),
            timeframe=str(self.config.get("timeframe") or self.spec.timeframe),
            config=self.config,
        )
        if signal.action in {"TRADE_LONG", "TRADE_SHORT"} and bool(self.config.get("allow_signal_generation", True)):
            return self._base_result(signal, "SIGNAL", [])
        code = signal.reasons[0] if signal.reasons else "blackcat_no_trade_setup"
        status = "SKIPPED" if code in {"insufficient_candles", "invalid_candle_data"} else "NO_SIGNAL"
        return self._base_result(signal, status, [_reject(code, code)])
