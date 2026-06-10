from __future__ import annotations

from typing import Any, Optional


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _demo_hint(value: Any) -> bool:
    return any(word in str(value or "").lower() for word in ["demo", "trial"])


def verify_demo_account(snapshot: Optional[dict[str, Any]]) -> dict[str, Any]:
    snapshot = _dict(snapshot)
    account = _dict(snapshot.get("account"))
    raw = _dict(snapshot.get("raw"))
    server = account.get("server") or account.get("account_server") or raw.get("account_server")
    name = account.get("name") or account.get("account_name") or raw.get("account_name")
    company = account.get("company") or account.get("account_company") or raw.get("account_company")
    trade_mode = account.get("trade_mode") or account.get("account_trade_mode") or raw.get("account_trade_mode")
    explicit = account.get("is_demo")
    if explicit is None:
        explicit = raw.get("is_demo")
    verified = bool(explicit) if isinstance(explicit, bool) else any(_demo_hint(v) for v in [server, name, company, trade_mode])
    reason = "demo account verified from MT5 metadata" if verified else "demo account could not be positively verified from MT5 snapshot"
    return {
        "demo_account_verified": verified,
        "demo_account_reason": reason,
        "account_login": account.get("login") or account.get("account_login"),
        "account_login_masked": _mask_login(account.get("login") or account.get("account_login")),
        "account_name": name,
        "account_server": server,
        "account_company": company,
        "account_currency": account.get("currency") or account.get("account_currency"),
        "account_trade_mode": trade_mode,
        "balance": account.get("balance"),
        "equity": account.get("equity"),
    }


def _mask_login(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return "*" * max(0, len(text) - 4) + text[-4:]
