from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any


DEFAULT_COOKIE_NAME = "aurix_dashboard_session"
DEFAULT_TTL_SECONDS = 86400


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class DashboardAuthConfig:
    password: str
    session_secret: str
    cookie_name: str = DEFAULT_COOKIE_NAME
    ttl_seconds: int = DEFAULT_TTL_SECONDS

    @classmethod
    def from_env(cls) -> "DashboardAuthConfig":
        return cls(
            password=os.getenv("AURIX_DASHBOARD_PASSWORD", ""),
            session_secret=os.getenv("AURIX_DASHBOARD_SESSION_SECRET", ""),
            cookie_name=os.getenv("AURIX_DASHBOARD_COOKIE_NAME", DEFAULT_COOKIE_NAME) or DEFAULT_COOKIE_NAME,
            ttl_seconds=_int_env("AURIX_DASHBOARD_SESSION_TTL_SECONDS", DEFAULT_TTL_SECONDS),
        )

    @property
    def configured(self) -> bool:
        return bool(self.password and self.session_secret)


def create_session_token(config: DashboardAuthConfig, *, now: int | None = None) -> str:
    issued_at = int(now if now is not None else time.time())
    payload = {
        "iat": issued_at,
        "exp": issued_at + max(1, int(config.ttl_seconds)),
        "nonce": secrets.token_urlsafe(16),
        "scope": "dashboard",
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64encode(payload_raw)
    signature = hmac.new(config.session_secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_part}.{_b64encode(signature)}"


def verify_session_token(token: str | None, config: DashboardAuthConfig, *, now: int | None = None) -> bool:
    if not token or not config.configured or "." not in token:
        return False
    payload_part, signature_part = token.split(".", 1)
    expected = hmac.new(config.session_secret.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64decode(signature_part)
        if not hmac.compare_digest(expected, provided):
            return False
        payload: dict[str, Any] = json.loads(_b64decode(payload_part).decode("utf-8"))
    except Exception:
        return False
    if payload.get("scope") != "dashboard":
        return False
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        return False
    return int(now if now is not None else time.time()) <= expires_at


def verify_dashboard_password(candidate: str, config: DashboardAuthConfig) -> bool:
    return bool(config.password) and hmac.compare_digest(candidate, config.password)


def build_cookie_header(
    *,
    config: DashboardAuthConfig,
    token: str,
    secure: bool,
    max_age: int | None = None,
) -> str:
    cookie = SimpleCookie()
    cookie[config.cookie_name] = token
    morsel = cookie[config.cookie_name]
    morsel["path"] = "/"
    morsel["httponly"] = True
    morsel["samesite"] = "Lax"
    morsel["max-age"] = str(config.ttl_seconds if max_age is None else max_age)
    if secure:
        morsel["secure"] = True
    return morsel.OutputString()


def build_clear_cookie_header(*, config: DashboardAuthConfig, secure: bool) -> str:
    return build_cookie_header(config=config, token="", secure=secure, max_age=0)

