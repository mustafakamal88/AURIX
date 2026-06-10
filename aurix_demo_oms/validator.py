from __future__ import annotations

from typing import Any

from .config import DemoOmsConfig
from .models import DemoOmsSafety, OmsOrderIntent, OmsRejectionReason, OmsValidationResult
from .state import count_open_oms_orders, count_today_requests


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reason(code: str, message: str) -> OmsRejectionReason:
    return OmsRejectionReason(code=code, message=message)


def validate_order_intent(
    intent: OmsOrderIntent,
    *,
    config: DemoOmsConfig,
    runtime_state: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    existing_requests: list[dict[str, Any]] | None = None,
    event_bus_enabled: bool = True,
) -> OmsValidationResult:
    reasons: list[OmsRejectionReason] = []
    warnings: list[str] = []
    runtime = _as_dict(runtime_state)
    market = _as_dict(runtime.get("market"))
    account_state = _as_dict(runtime.get("account"))
    snapshot_data = _as_dict(snapshot)
    snapshot_account = _as_dict(snapshot_data.get("account"))
    tick = _as_dict(snapshot_data.get("tick")) or _as_dict(market.get("latest_tick")) or _as_dict(market.get("quality"))
    account = snapshot_account or account_state
    positions = _as_list(snapshot_data.get("positions")) or _as_list(_as_dict(runtime.get("positions")).get("items"))
    requests = existing_requests or []
    spread_points = _as_float(tick.get("spread_points"))
    account_currency = account.get("currency")
    open_oms_orders = count_open_oms_orders(requests, intent.symbol if config.require_no_open_oms_order_for_symbol else None)
    trades_today = count_today_requests(requests)

    if not config.enabled:
        reasons.append(_reason("config_disabled", "Demo OMS is disabled"))
    if config.mode != "DEMO_OMS_DRY_RUN":
        reasons.append(_reason("mode_not_dry_run", f"Demo OMS mode must be DEMO_OMS_DRY_RUN, got {config.mode}"))
    if config.require_event_bus_enabled and not event_bus_enabled:
        reasons.append(_reason("event_bus_disabled", "Event bus is required but disabled"))
    if config.require_symbol_match and intent.symbol != config.symbol:
        reasons.append(_reason("symbol_mismatch", f"signal symbol {intent.symbol} does not match {config.symbol}"))
    if config.require_account_currency_match and account_currency and account_currency != config.account_currency:
        reasons.append(_reason("account_currency_mismatch", f"account currency {account_currency} does not match {config.account_currency}"))
    if config.require_account_currency_match and not account_currency:
        warnings.append("account currency unavailable")
    if intent.strategy_name not in config.allowed_strategies:
        reasons.append(_reason("strategy_not_allowed", f"strategy is not allowed: {intent.strategy_name}"))
    if intent.direction not in {"BUY", "SELL"}:
        reasons.append(_reason("direction_not_allowed", f"direction must be BUY or SELL, got {intent.direction}"))
    if intent.order_type not in config.allowed_order_types:
        reasons.append(_reason("order_type_not_allowed", f"order type is not allowed: {intent.order_type}"))
    if intent.entry_reference is None:
        reasons.append(_reason("entry_reference_missing", "entry reference is required"))
    if intent.stop_loss is None:
        reasons.append(_reason("stop_loss_missing", "stop loss is required"))
    if intent.take_profit is None:
        reasons.append(_reason("take_profit_missing", "take profit is required"))
    if intent.volume <= 0 or intent.volume > config.max_volume:
        reasons.append(_reason("volume_above_max", f"volume {intent.volume} exceeds max_volume {config.max_volume}"))
    if spread_points is None:
        reasons.append(_reason("risk_governor_validation_unavailable", "spread is unavailable for validation-only risk check"))
    elif spread_points > config.max_spread_points:
        reasons.append(_reason("spread_above_max", f"spread {spread_points} exceeds max_spread_points {config.max_spread_points}"))
    if trades_today >= config.max_trades_per_day:
        reasons.append(_reason("max_trades_per_day_reached", f"OMS dry-run requests today {trades_today} reached max_trades_per_day {config.max_trades_per_day}"))
    if open_oms_orders >= config.max_open_orders:
        reasons.append(_reason("max_open_orders_reached", f"open OMS orders {open_oms_orders} reached max_open_orders {config.max_open_orders}"))
    if config.require_no_open_broker_position_for_symbol and positions:
        reasons.append(_reason("open_broker_position_for_symbol", "open broker position exists for symbol"))
    if config.allow_demo_execution:
        reasons.append(_reason("demo_execution_enabled", "demo execution must remain disabled in Part 30"))
    if config.allow_live_execution:
        reasons.append(_reason("live_execution_enabled", "live execution must remain disabled"))
    if config.allow_real_account_execution:
        reasons.append(_reason("real_account_execution_enabled", "real account execution must remain disabled"))
    if config.allow_command_queueing or config.allow_demo_command_queueing:
        reasons.append(_reason("command_queueing_enabled", "command queueing must remain disabled"))
    if config.allow_live_arming:
        reasons.append(_reason("live_arming_enabled", "live arming must remain disabled"))

    raw = _as_dict(snapshot_data.get("raw"))
    ea_broker_execution = raw.get("broker_execution_enabled")
    if config.require_ea_live_trading_disabled_now and ea_broker_execution is True:
        reasons.append(_reason("ea_live_trading_enabled", "EA reports AURIX_BROKER_EXECUTION=true"))

    risk_checked = spread_points is not None and bool(account or snapshot_data or runtime)
    risk_approved = risk_checked and not any(reason.code in {"risk_governor_validation_unavailable", "spread_above_max"} for reason in reasons)
    if config.require_risk_governor_approval and not risk_checked:
        if not any(reason.code == "risk_governor_validation_unavailable" for reason in reasons):
            reasons.append(_reason("risk_governor_validation_unavailable", "risk governor validation context is unavailable"))
    if config.require_risk_governor_approval and not risk_approved and not reasons:
        reasons.append(_reason("risk_governor_validation_unavailable", "risk governor validation failed closed"))

    approved = len(reasons) == 0
    return OmsValidationResult(
        intent_id=intent.id,
        approved=approved,
        status="APPROVE" if approved else "BLOCK",
        rejection_reasons=reasons,
        warnings=warnings,
        risk_governor_checked=risk_checked,
        risk_governor_approved=risk_approved and approved,
        risk_governor_decision="APPROVE" if risk_approved and approved else "BLOCK",
        spread_points=spread_points,
        account_currency=account_currency,
        open_oms_orders=open_oms_orders,
        trades_today=trades_today,
        safety=DemoOmsSafety(),
    )
