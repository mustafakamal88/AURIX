from __future__ import annotations

from typing import Any, Optional


def _float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_daily_risk(snapshot: Optional[dict[str, Any]], config: Any, store: Any) -> dict[str, Any]:
    account = (snapshot or {}).get("account") or {}
    balance = _float(account.get("balance"))
    equity = _float(account.get("equity"))
    baseline = store.get_or_create_daily_baseline(balance=balance, equity=equity)
    start_equity = _float(baseline.get("start_equity"))
    if equity is None or start_equity is None or start_equity <= 0:
        return {"status": "BLOCKED", "allowed": False, "reason": "account equity baseline unavailable", "baseline": baseline}
    equity_loss = max(0.0, start_equity - equity)
    drawdown_percent = (equity_loss / start_equity) * 100.0
    daily_risk_limit_percent = float(getattr(config, "daily_risk_limit_percent", 10.0))
    daily_loss_limit = start_equity * (daily_risk_limit_percent / 100.0)
    loss_ok = equity_loss <= daily_loss_limit
    drawdown_ok = drawdown_percent <= daily_risk_limit_percent
    allowed = loss_ok and drawdown_ok
    return {
        "status": "OK" if allowed else "BLOCKED",
        "allowed": allowed,
        "reason": "daily risk guard passed" if allowed else "daily loss/drawdown guard breached",
        "start_equity": start_equity,
        "current_equity": equity,
        "equity_loss": round(equity_loss, 4),
        "drawdown_percent": round(drawdown_percent, 4),
        "daily_loss_limit": round(daily_loss_limit, 4),
        "daily_risk_limit_percent": daily_risk_limit_percent,
    }
