from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from aurix_common.persistence import write_json_atomic


def _float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_daily_risk(snapshot: Optional[dict[str, Any]], config: Any, store: Any) -> dict[str, Any]:
    account = (snapshot or {}).get("account") or {}
    received_at = (snapshot or {}).get("received_at")
    tick = (snapshot or {}).get("tick") or {}
    snapshot_age = min([item for item in [_age_seconds(received_at), _age_seconds(tick.get("time"))] if item is not None], default=None)
    balance = _float(account.get("balance"))
    equity = _float(account.get("equity"))
    baseline = store.get_or_create_daily_baseline(balance=balance, equity=equity)
    start_equity = _float(baseline.get("start_equity"))
    risk_per_trade_percent = float(getattr(config, "risk_per_trade_percent", 2.0))
    daily_risk_limit_percent = float(getattr(config, "daily_risk_limit_percent", 10.0))
    currency = account.get("currency")
    reasons: list[str] = []
    if equity is None:
        reasons.append("current equity missing")
    if start_equity is None or start_equity <= 0:
        reasons.append("daily equity baseline unavailable")
    if snapshot_age is None:
        reasons.append("account snapshot timestamp missing")
    elif snapshot_age > 180:
        reasons.append("account snapshot stale")
    snapshot_stale_or_missing = snapshot_age is None or snapshot_age > 180
    if equity is None or start_equity is None or start_equity <= 0 or snapshot_stale_or_missing:
        state = {
            "generated_at": _utc_now_iso(),
            "trading_day": datetime.now(timezone.utc).date().isoformat(),
            "account_currency": currency,
            "starting_equity": start_equity,
            "current_equity": equity,
            "realized_pnl_today": 0.0,
            "floating_pnl": _float(account.get("profit")) or 0.0,
            "equity_loss": round(max(0.0, start_equity - equity), 4) if equity is not None and start_equity else None,
            "equity_loss_pct": round((max(0.0, start_equity - equity) / start_equity) * 100.0, 4) if equity is not None and start_equity else None,
            "per_trade_risk_pct": risk_per_trade_percent,
            "daily_loss_limit_pct": daily_risk_limit_percent,
            "per_trade_risk_amount": round(start_equity * (risk_per_trade_percent / 100.0), 4) if start_equity else None,
            "daily_loss_limit_amount": round(start_equity * (daily_risk_limit_percent / 100.0), 4) if start_equity else None,
            "risk_used_today_amount": None,
            "remaining_daily_risk_amount": None,
            "status": "UNKNOWN",
            "allowed": False,
            "reason": "; ".join(reasons) or "account equity baseline unavailable",
            "reasons": reasons or ["account equity baseline unavailable"],
            "baseline": baseline,
        }
        _write_daily_risk_state(store, state)
        return state
    equity_loss = max(0.0, start_equity - equity)
    drawdown_percent = (equity_loss / start_equity) * 100.0
    daily_loss_limit = start_equity * (daily_risk_limit_percent / 100.0)
    loss_ok = equity_loss < daily_loss_limit
    drawdown_ok = drawdown_percent < daily_risk_limit_percent
    allowed = loss_ok and drawdown_ok
    if not allowed:
        reasons.append("daily loss limit reached or exceeded")
    state = {
        "generated_at": _utc_now_iso(),
        "trading_day": datetime.now(timezone.utc).date().isoformat(),
        "account_currency": currency,
        "starting_equity": start_equity,
        "current_equity": equity,
        "realized_pnl_today": 0.0,
        "floating_pnl": _float(account.get("profit")) or 0.0,
        "equity_loss": round(equity_loss, 4),
        "equity_loss_pct": round(drawdown_percent, 4),
        "per_trade_risk_pct": risk_per_trade_percent,
        "daily_loss_limit_pct": daily_risk_limit_percent,
        "per_trade_risk_amount": round(start_equity * (risk_per_trade_percent / 100.0), 4),
        "daily_loss_limit_amount": round(daily_loss_limit, 4),
        "risk_used_today_amount": round(equity_loss, 4),
        "remaining_daily_risk_amount": round(max(daily_loss_limit - equity_loss, 0.0), 4),
        "status": "READY" if allowed else "BLOCKED",
        "allowed": allowed,
        "reason": "daily risk guard passed" if allowed else "daily loss/drawdown guard breached",
        "reasons": reasons,
        "start_equity": start_equity,
        "current_equity": equity,
        "equity_loss": round(equity_loss, 4),
        "drawdown_percent": round(drawdown_percent, 4),
        "daily_loss_limit": round(daily_loss_limit, 4),
        "daily_risk_limit_percent": daily_risk_limit_percent,
    }
    _write_daily_risk_state(store, state)
    return state


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_seconds(value: Any) -> float | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        try:
            return max(0.0, (datetime.now(timezone.utc) - datetime.fromtimestamp(float(value), tz=timezone.utc)).total_seconds())
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())


def _write_daily_risk_state(store: Any, state: dict[str, Any]) -> None:
    root = getattr(store, "root", None)
    if root is None:
        return
    data_dir = Path(root).parent
    risk_dir = data_dir / "risk"
    risk_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(risk_dir / "daily_risk_state.json", state)
