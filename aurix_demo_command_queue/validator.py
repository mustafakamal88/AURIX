from __future__ import annotations

from typing import Any

from .config import DemoCommandQueueConfig
from .models import DemoCommandPreview, DemoCommandQueueRejection, DemoCommandValidationResult


def _reason(code: str, message: str) -> DemoCommandQueueRejection:
    return DemoCommandQueueRejection(code=code, message=message)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_command_preview(
    preview: DemoCommandPreview,
    *,
    config: DemoCommandQueueConfig,
    oms_request: dict[str, Any] | None,
    broker_reconciliation: dict[str, Any] | None,
    snapshot: dict[str, Any] | None,
) -> DemoCommandValidationResult:
    reasons: list[DemoCommandQueueRejection] = []
    warnings: list[str] = []
    snap = _as_dict(snapshot)
    account = _as_dict(snap.get("account"))
    tick = _as_dict(snap.get("tick"))
    positions = _as_list(snap.get("positions"))
    orders = _as_list(snap.get("orders"))
    raw = _as_dict(snap.get("raw"))

    if not config.enabled:
        reasons.append(_reason("config_disabled", "demo command queue is disabled"))
    if config.mode != "DEMO_COMMAND_QUEUE_DRY_RUN":
        reasons.append(_reason("mode_not_dry_run", f"mode must be DEMO_COMMAND_QUEUE_DRY_RUN, got {config.mode}"))
    if not config.allow_command_preview:
        reasons.append(_reason("command_preview_disabled", "command preview is disabled"))
    for flag, code in [
        (config.allow_demo_execution, "demo_execution_enabled"),
        (config.allow_live_execution, "live_execution_enabled"),
        (config.allow_live_arming, "live_arming_enabled"),
        (config.allow_real_account_execution, "real_account_execution_enabled"),
    ]:
        if flag:
            reasons.append(_reason(code, f"safety config violation: {code}"))
    if config.require_manual_demo_arm and not config.manual_demo_arm:
        reasons.append(_reason("manual_demo_arm_false", "manual demo arm is false"))
    if not config.allow_demo_command_queueing:
        reasons.append(_reason("demo_command_queueing_disabled", "demo command queueing is disabled"))
    if not config.allow_mt5_command_queueing:
        reasons.append(_reason("mt5_command_queueing_disabled", "MT5 command queueing is disabled"))
    if config.require_broker_reconciliation_clean and _as_dict(broker_reconciliation).get("status") != "CLEAN":
        reasons.append(_reason("broker_reconciliation_not_clean", "broker reconciliation must be CLEAN"))
    if config.require_demo_oms_request and not oms_request:
        reasons.append(_reason("demo_oms_request_missing", "Demo OMS request is required"))
    if config.require_demo_oms_request_dry_run and _as_dict(oms_request).get("status") not in {"DRY_RUN_ONLY", "READY_FOR_DEMO_ONLY"}:
        reasons.append(_reason("demo_oms_request_not_dry_run", "Demo OMS request is not dry-run ready"))
    if config.require_mt5_command_id_null and _as_dict(oms_request).get("mt5_command_id") is not None:
        reasons.append(_reason("mt5_command_id_present", "OMS request mt5_command_id must be null"))
    if config.require_broker_order_id_null and _as_dict(oms_request).get("broker_order_id") is not None:
        reasons.append(_reason("broker_order_id_present", "OMS request broker_order_id must be null"))
    if config.require_symbol_match and preview.symbol != config.symbol:
        reasons.append(_reason("symbol_mismatch", f"symbol {preview.symbol} does not match {config.symbol}"))
    if config.require_account_currency_match and account.get("currency") and account.get("currency") != config.account_currency:
        reasons.append(_reason("account_currency_mismatch", f"account currency {account.get('currency')} does not match {config.account_currency}"))
    elif not account.get("currency"):
        warnings.append("account currency unavailable")
    if preview.order_type not in config.allowed_order_types:
        reasons.append(_reason("order_type_not_allowed", f"order type not allowed: {preview.order_type}"))
    if preview.volume <= 0 or (config.require_max_volume and preview.volume > config.max_volume):
        reasons.append(_reason("volume_above_max", f"volume {preview.volume} exceeds max_volume {config.max_volume}"))
    spread = _as_float(tick.get("spread_points"))
    if spread is not None and spread > config.max_spread_points:
        reasons.append(_reason("spread_above_max", f"spread {spread} exceeds max_spread_points {config.max_spread_points}"))
    if raw.get("broker_execution_enabled") is True and config.require_ea_live_trading_disabled_now:
        reasons.append(_reason("ea_live_trading_enabled", "EA reports AURIX_BROKER_EXECUTION=true"))
    symbol_positions = [item for item in positions if _as_dict(item).get("symbol") == config.symbol]
    symbol_orders = [item for item in orders if _as_dict(item).get("symbol") == config.symbol]
    if config.require_no_open_broker_position_for_symbol and len(symbol_positions) > config.max_open_broker_positions:
        reasons.append(_reason("open_broker_position", "open broker position exists for symbol"))
    if config.require_no_open_broker_order_for_symbol and len(symbol_orders) > config.max_open_broker_orders:
        reasons.append(_reason("open_broker_order", "open broker order exists for symbol"))

    approved = len(reasons) == 0
    return DemoCommandValidationResult(preview_id=preview.id, approved=approved, status="APPROVE" if approved else "BLOCK", rejection_reasons=reasons, warnings=warnings)
