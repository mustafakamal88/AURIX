from __future__ import annotations

from typing import Any, Optional

from aurix_bridge_server.models import Command, utc_now_iso
from aurix_paper_risk_audit import PaperRiskDecision
from aurix_risk_governor import RiskGovernor
from aurix_risk_governor.config import RiskConfig
from aurix_strategy_engine.models import StrategySignal

from .config import PaperTradingConfig
from .models import PaperTrade


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class PaperTradingEngine:
    def __init__(self, config: PaperTradingConfig, risk_config: RiskConfig):
        self.config = config
        self.risk_governor = RiskGovernor(risk_config)

    def status(self, snapshot: Optional[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
        tick = as_dict(snapshot.get("tick")) if snapshot else {}
        open_trades = [trade for trade in trades if trade.get("status") == "OPEN"]
        closed_trades = [trade for trade in trades if trade.get("status") != "OPEN"]
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "snapshot_received_at": snapshot.get("received_at") if snapshot else None,
            "snapshot_symbol": tick.get("symbol") if tick else None,
            "bid": tick.get("bid") if tick else None,
            "ask": tick.get("ask") if tick else None,
            "open_trades": len(open_trades),
            "closed_trades": len(closed_trades),
            "max_open_paper_trades": self.config.max_open_paper_trades,
            "config": self.config.model_dump(),
        }

    def create_from_signal(
        self,
        signal: StrategySignal,
        snapshot: Optional[dict[str, Any]],
        open_trades: list[dict[str, Any]],
        previous_risk_decisions: list[dict[str, Any]],
    ) -> tuple[Optional[PaperTrade], dict[str, Any]]:
        if not self.config.enabled:
            return None, {"created": False, "reason": "paper trading disabled", "signal": signal.model_dump()}

        if signal.status not in {"SHADOW_SIGNAL", "PAPER_SIGNAL"} or signal.direction not in {"BUY", "SELL"}:
            return None, {"created": False, "reason": "signal is not actionable", "signal": signal.model_dump()}

        if signal.symbol != self.config.symbol:
            return None, {"created": False, "reason": f"signal symbol {signal.symbol} does not match {self.config.symbol}", "signal": signal.model_dump()}

        if len(open_trades) >= self.config.max_open_paper_trades:
            return None, {"created": False, "reason": "max open paper trades reached", "signal": signal.model_dump()}

        if not self.config.allow_multiple_same_direction:
            for trade in open_trades:
                if trade.get("direction") == signal.direction:
                    return None, {"created": False, "reason": "same direction paper trade already open", "signal": signal.model_dump()}

        tick = as_dict(snapshot.get("tick")) if snapshot else {}
        bid = as_float(tick.get("bid"))
        ask = as_float(tick.get("ask"))
        point = as_float(tick.get("point")) or 0.01
        if bid is None or ask is None or bid <= 0 or ask <= 0:
            return None, {"created": False, "reason": "snapshot bid/ask missing", "signal": signal.model_dump()}

        entry = signal.entry_reference or (ask if signal.direction == "BUY" else bid)
        stop_distance = self.config.default_stop_points * point
        take_profit_distance = self.config.default_take_profit_points * point
        if signal.direction == "BUY":
            stop_loss = signal.stop_loss_reference or (entry - stop_distance)
            take_profit = signal.take_profit_reference or (entry + take_profit_distance)
        else:
            stop_loss = signal.stop_loss_reference or (entry + stop_distance)
            take_profit = signal.take_profit_reference or (entry - take_profit_distance)

        risk_command = Command(
            type="OPEN_MARKET",
            terminal_id=str(snapshot.get("terminal_id") if snapshot else "AURIX-MAC-001"),
            symbol=signal.symbol,
            direction=signal.direction,
            volume=self.config.default_volume,
            sl=stop_loss,
            tp=take_profit,
            comment="AURIX-PAPER-SIMULATION",
            live_confirm=None,
        )
        risk_decision = self.risk_governor.evaluate_open_market(risk_command, snapshot, previous_risk_decisions)
        if not risk_decision.approved:
            paper_risk_decision = self._paper_risk_decision(
                signal=signal,
                snapshot=snapshot,
                trade_id=None,
                entry=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_status="REJECTED",
                risk_reason="; ".join(risk_decision.reasons) or "simulated risk check rejected paper trade",
                risk_decision=risk_decision.model_dump(),
            )
            return None, {
                "created": False,
                "reason": "simulated risk check blocked paper trade",
                "risk_decision": risk_decision.model_dump(),
                "paper_risk_decision": paper_risk_decision.model_dump(),
                "signal": signal.model_dump(),
            }

        trade = PaperTrade(
            signal_id=signal.id,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=self.config.default_volume,
            strategy_id=signal.strategy_id or signal.strategy_name,
            signal_confidence=signal.signal_confidence if signal.signal_confidence is not None else signal.confidence,
            signal_reasons=signal.signal_reasons or list(signal.reasons),
            decision_cycle_id=signal.decision_cycle_id,
            final_gate_result=signal.final_gate_result or "PAPER_RISK_APPROVED",
            reasons=["created from paper signal" if signal.status == "PAPER_SIGNAL" else "created from shadow signal", *signal.reasons],
            snapshot_opened_at=snapshot.get("received_at") if snapshot else None,
        )
        paper_risk_decision = self._paper_risk_decision(
            signal=signal,
            snapshot=snapshot,
            trade_id=trade.id,
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_status="APPROVED",
            risk_reason="simulated risk check approved paper trade",
            risk_decision=risk_decision.model_dump(),
        )
        trade.risk_decision_id = paper_risk_decision.id
        signal.paper_risk_checked = True
        signal.paper_risk_decision_id = paper_risk_decision.id
        signal.paper_risk_status = paper_risk_decision.risk_status
        signal.paper_risk_checked_at = paper_risk_decision.created_at
        signal.risk_check_source = "PAPER_ENGINE_SIMULATION"
        return trade, {
            "created": True,
            "paper_trade": trade.model_dump(),
            "risk_decision": risk_decision.model_dump(),
            "paper_risk_decision": paper_risk_decision.model_dump(),
            "signal": signal.model_dump(),
        }

    def _paper_risk_decision(
        self,
        *,
        signal: StrategySignal,
        snapshot: Optional[dict[str, Any]],
        trade_id: Optional[str],
        entry: float,
        stop_loss: float,
        take_profit: float,
        risk_status: str,
        risk_reason: str,
        risk_decision: dict[str, Any],
    ) -> PaperRiskDecision:
        account = as_dict(snapshot.get("account")) if snapshot else {}
        tick = as_dict(snapshot.get("tick")) if snapshot else {}
        return PaperRiskDecision(
            symbol=signal.symbol,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            signal_id=signal.id,
            trade_id=trade_id,
            direction=str(signal.direction),
            entry_reference=entry,
            stop_loss_reference=stop_loss,
            take_profit_reference=take_profit,
            volume=self.config.default_volume,
            risk_status=risk_status,  # type: ignore[arg-type]
            risk_reason=risk_reason,
            checks={
                "risk_governor_decision": risk_decision.get("decision"),
                "risk_governor_approved": risk_decision.get("approved"),
                "risk_governor_reasons": risk_decision.get("reasons") or [],
            },
            limits={
                "max_open_paper_trades": self.config.max_open_paper_trades,
                "allow_multiple_same_direction": self.config.allow_multiple_same_direction,
                "default_volume": self.config.default_volume,
            },
            account_snapshot={
                "balance": account.get("balance"),
                "equity": account.get("equity"),
                "currency": account.get("currency"),
                "login": account.get("login"),
                "server": account.get("server"),
            },
            market_snapshot={
                "symbol": tick.get("symbol"),
                "bid": tick.get("bid"),
                "ask": tick.get("ask"),
                "spread_points": tick.get("spread_points"),
                "snapshot_received_at": snapshot.get("received_at") if snapshot else None,
            },
            safety={
                "paper_audit_only": True,
                "mode": "PAPER",
                "mt5_commands_queued": False,
                "broker_order_created": False,
                "open_market_endpoint_called": False,
            },
        )

    def update_open_trades(self, snapshot: Optional[dict[str, Any]], trades: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if snapshot is None:
            return trades, []

        tick = as_dict(snapshot.get("tick"))
        bid = as_float(tick.get("bid"))
        ask = as_float(tick.get("ask"))
        if bid is None or ask is None:
            return trades, []

        updated: list[dict[str, Any]] = []
        for trade in trades:
            if trade.get("status") != "OPEN":
                continue

            direction = trade.get("direction")
            close_price: Optional[float] = None
            status: Optional[str] = None

            if direction == "BUY":
                if bid >= float(trade["take_profit"]):
                    close_price = float(trade["take_profit"])
                    status = "CLOSED_TP"
                elif bid <= float(trade["stop_loss"]):
                    close_price = float(trade["stop_loss"])
                    status = "CLOSED_SL"
            elif direction == "SELL":
                if ask <= float(trade["take_profit"]):
                    close_price = float(trade["take_profit"])
                    status = "CLOSED_TP"
                elif ask >= float(trade["stop_loss"]):
                    close_price = float(trade["stop_loss"])
                    status = "CLOSED_SL"

            if status and close_price is not None:
                self._close_trade(trade, status, close_price, snapshot)
                updated.append(trade.copy())

        return trades, updated

    def close_manual(self, trade: dict[str, Any], snapshot: Optional[dict[str, Any]]) -> dict[str, Any]:
        tick = as_dict(snapshot.get("tick")) if snapshot else {}
        direction = trade.get("direction")
        price = as_float(tick.get("bid" if direction == "BUY" else "ask"))
        if price is None:
            price = float(trade["entry_price"])
        self._close_trade(trade, "CLOSED_MANUAL", price, snapshot or {})
        return trade

    def _close_trade(self, trade: dict[str, Any], status: str, close_price: float, snapshot: dict[str, Any]) -> None:
        entry = float(trade["entry_price"])
        stop_loss = float(trade["stop_loss"])
        direction = trade.get("direction")
        if direction == "BUY":
            pnl_points = close_price - entry
            risk_points = entry - stop_loss
        else:
            pnl_points = entry - close_price
            risk_points = stop_loss - entry

        trade["status"] = status
        trade["closed_at"] = utc_now_iso()
        trade["close_price"] = close_price
        trade["pnl_points"] = pnl_points
        trade["r_multiple"] = (pnl_points / risk_points) if risk_points else None
        trade["snapshot_closed_at"] = snapshot.get("received_at")
