from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .config import JournalConfig
from .models import JournalEntry, MistakeFlag, ReviewClassification


class JournalReviewer:
    def __init__(self, config: JournalConfig):
        self.config = config

    def review_paper_trades(
        self,
        trades: list[dict[str, Any]],
        signals: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
        market_quality: dict[str, Any],
    ) -> list[JournalEntry]:
        if not self.config.enabled or not self.config.review_paper_trades:
            return []

        signals_by_id = {str(signal.get("id")): signal for signal in signals if signal.get("id")}
        context_by_snapshot_time = {
            str(context.get("snapshot_updated_at")): context for context in contexts if context.get("snapshot_updated_at")
        }
        return [
            self._paper_trade_entry(trade, signals_by_id.get(str(trade.get("signal_id"))), context_by_snapshot_time, market_quality)
            for trade in trades
            if str(trade.get("symbol") or self.config.symbol) == self.config.symbol
        ]

    def review_signals(
        self,
        signals: list[dict[str, Any]],
        trades: list[dict[str, Any]],
        contexts: list[dict[str, Any]],
        market_quality: dict[str, Any],
    ) -> list[JournalEntry]:
        if not self.config.enabled or not self.config.review_signals:
            return []

        traded_signal_ids = {str(trade.get("signal_id")) for trade in trades if trade.get("signal_id")}
        context_by_snapshot_time = {
            str(context.get("snapshot_updated_at")): context for context in contexts if context.get("snapshot_updated_at")
        }
        return [
            self._signal_entry(signal, str(signal.get("id")) in traded_signal_ids, context_by_snapshot_time, market_quality)
            for signal in signals
            if str(signal.get("symbol") or self.config.symbol) == self.config.symbol
        ]

    def daily_summary(
        self,
        trades: list[dict[str, Any]],
        signals: list[dict[str, Any]],
        analytics_report: dict[str, Any],
        market_quality: dict[str, Any],
        now: Optional[datetime] = None,
    ) -> JournalEntry:
        current = now or datetime.now(timezone.utc)
        day = current.date().isoformat()
        today_trades = [trade for trade in trades if _date_part(trade.get("opened_at")) == day or _date_part(trade.get("closed_at")) == day]
        today_signals = [signal for signal in signals if _date_part(signal.get("created_at")) == day]
        closed = [trade for trade in today_trades if str(trade.get("status", "")).startswith("CLOSED")]
        wins = [trade for trade in closed if _as_float(trade.get("r_multiple")) and (_as_float(trade.get("r_multiple")) or 0) > 0]
        losses = [trade for trade in closed if _as_float(trade.get("r_multiple")) and (_as_float(trade.get("r_multiple")) or 0) < 0]
        total_r = sum(_as_float(trade.get("r_multiple")) or 0.0 for trade in closed)
        warnings = list(analytics_report.get("warnings") or [])
        if market_quality and not market_quality.get("ok"):
            warnings.extend(str(reason) for reason in market_quality.get("reasons") or [])

        return JournalEntry(
            entry_type="DAILY_SUMMARY",
            source_id=day,
            symbol=self.config.symbol,
            status="SUMMARY",
            setup_name="daily_paper_review",
            classification="UNKNOWN",
            mistake_flags=["NONE"],
            strengths=[f"wins={len(wins)}"] if wins else [],
            weaknesses=[f"losses={len(losses)}"] if losses else [],
            notes=[
                f"total_signals={len(today_signals)}",
                f"paper_trades={len(today_trades)}",
                f"wins={len(wins)}",
                f"losses={len(losses)}",
                f"total_r={round(total_r, 6)}",
                f"warnings={'; '.join(warnings) if warnings else 'none'}",
            ],
        )

    def _paper_trade_entry(
        self,
        trade: dict[str, Any],
        signal: Optional[dict[str, Any]],
        context_by_snapshot_time: dict[str, dict[str, Any]],
        market_quality: dict[str, Any],
    ) -> JournalEntry:
        context = context_by_snapshot_time.get(str(trade.get("snapshot_opened_at"))) if self.config.include_context else None
        session = _first_present(signal, "context_session", context, "session_name")
        regime = _first_present(signal, "context_regime", context, "regime")
        bias = _first_present(signal, "context_bias", context, "directional_bias")
        classification = self._classify_trade(trade)
        flags = self._mistake_flags(
            session=session,
            spread_high=_market_spread_high(market_quality) if self.config.include_market_quality else False,
            context_present=bool(session or regime or bias),
            stop_loss=trade.get("stop_loss"),
            take_profit=trade.get("take_profit"),
            confidence=signal.get("confidence") if signal else None,
        )
        return JournalEntry(
            entry_type="PAPER_TRADE",
            source_id=str(trade.get("id") or ""),
            symbol=trade.get("symbol"),
            direction=trade.get("direction"),
            status=trade.get("status"),
            session=session,
            regime=regime,
            bias=bias,
            setup_name=trade.get("strategy_name"),
            entry_price=_as_float(trade.get("entry_price")),
            stop_loss=_as_float(trade.get("stop_loss")),
            take_profit=_as_float(trade.get("take_profit")),
            close_price=_as_float(trade.get("close_price")),
            pnl_points=_as_float(trade.get("pnl_points")),
            r_multiple=_as_float(trade.get("r_multiple")),
            classification=classification,
            mistake_flags=flags,
            strengths=self._trade_strengths(classification),
            weaknesses=self._trade_weaknesses(flags),
            notes=list(trade.get("reasons") or []),
        )

    def _signal_entry(
        self,
        signal: dict[str, Any],
        has_trade: bool,
        context_by_snapshot_time: dict[str, dict[str, Any]],
        market_quality: dict[str, Any],
    ) -> JournalEntry:
        context = context_by_snapshot_time.get(str(signal.get("snapshot_updated_at"))) if self.config.include_context else None
        session = signal.get("context_session") or (context or {}).get("session_name")
        regime = signal.get("context_regime") or (context or {}).get("regime")
        bias = signal.get("context_bias") or (context or {}).get("directional_bias")
        classification = self._classify_signal(signal, has_trade)
        flags = self._mistake_flags(
            session=session,
            spread_high=_market_spread_high(market_quality) if self.config.include_market_quality else False,
            context_present=bool(session or regime or bias),
            stop_loss=signal.get("stop_loss_reference"),
            take_profit=signal.get("take_profit_reference"),
            confidence=signal.get("confidence"),
        )
        return JournalEntry(
            entry_type="SIGNAL",
            source_id=str(signal.get("id") or ""),
            symbol=signal.get("symbol"),
            direction=signal.get("direction"),
            status=signal.get("status"),
            session=session,
            regime=regime,
            bias=bias,
            setup_name=signal.get("strategy_name"),
            entry_price=_as_float(signal.get("entry_reference")),
            stop_loss=_as_float(signal.get("stop_loss_reference")),
            take_profit=_as_float(signal.get("take_profit_reference")),
            classification=classification,
            mistake_flags=flags,
            strengths=["actionable paper signal"] if signal.get("status") == "SHADOW_SIGNAL" else [],
            weaknesses=self._trade_weaknesses(flags),
            notes=list(signal.get("reasons") or []),
        )

    def _classify_trade(self, trade: dict[str, Any]) -> ReviewClassification:
        status = str(trade.get("status") or "")
        if status == "OPEN":
            return "OPEN_TRADE"
        if status == "CLOSED_TP":
            return "VALID_WIN"
        if status == "CLOSED_SL":
            return "VALID_LOSS"
        r_multiple = _as_float(trade.get("r_multiple"))
        if r_multiple is not None and r_multiple > 0:
            return "VALID_WIN"
        if r_multiple is not None and r_multiple < 0:
            return "VALID_LOSS"
        return "UNKNOWN"

    def _classify_signal(self, signal: dict[str, Any], has_trade: bool) -> ReviewClassification:
        reasons = " ".join(str(reason).lower() for reason in signal.get("reasons") or [])
        status = str(signal.get("status") or "")
        if "session is closed" in reasons:
            return "SESSION_BLOCKED"
        if "spread" in reasons and ("exceeds" in reasons or status == "SKIPPED_SPREAD"):
            return "HIGH_SPREAD_BLOCKED"
        if "insufficient" in reasons or "need at least" in reasons or status == "SKIPPED_INSUFFICIENT_DATA":
            return "INSUFFICIENT_DATA"
        if status == "NO_SIGNAL":
            return "NO_SIGNAL"
        if status == "SHADOW_SIGNAL" and not has_trade:
            return "NO_TRADE"
        return "UNKNOWN"

    def _mistake_flags(
        self,
        *,
        session: Any,
        spread_high: bool,
        context_present: bool,
        stop_loss: Any,
        take_profit: Any,
        confidence: Any,
    ) -> list[MistakeFlag]:
        flags: list[MistakeFlag] = []
        if session == "CLOSED":
            flags.append("TRADED_CLOSED_SESSION")
        if spread_high:
            flags.append("HIGH_SPREAD")
        if not context_present:
            flags.append("NO_CONTEXT")
        if _as_float(stop_loss) is None:
            flags.append("NO_STOP_LOSS")
        if _as_float(take_profit) is None:
            flags.append("NO_TAKE_PROFIT")
        if (_as_float(confidence) or 0.0) < 0.5:
            flags.append("LOW_CONFIDENCE")
        return flags or ["NONE"]

    def _trade_strengths(self, classification: ReviewClassification) -> list[str]:
        if classification == "VALID_WIN":
            return ["paper setup reached take profit or positive R"]
        if classification == "OPEN_TRADE":
            return ["paper trade remains open for tracking"]
        return []

    def _trade_weaknesses(self, flags: list[MistakeFlag]) -> list[str]:
        return [] if flags == ["NONE"] else [flag.lower() for flag in flags]


def _first_present(primary: Optional[dict[str, Any]], primary_key: str, secondary: Optional[dict[str, Any]], secondary_key: str) -> Any:
    if primary and primary.get(primary_key):
        return primary.get(primary_key)
    if secondary and secondary.get(secondary_key):
        return secondary.get(secondary_key)
    return None


def _market_spread_high(market_quality: dict[str, Any]) -> bool:
    if market_quality.get("spread_ok") is False:
        return True
    return any("spread" in str(reason).lower() for reason in market_quality.get("reasons") or [])


def _date_part(value: Any) -> Optional[str]:
    if not value:
        return None
    return str(value)[:10]


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
