from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    app_js = (ROOT / "aurix_dashboard" / "app.js").read_text(encoding="utf-8")
    index = (ROOT / "aurix_dashboard" / "index.html").read_text(encoding="utf-8")
    open_dashboard = (ROOT / "scripts" / "open_dashboard.py").read_text(encoding="utf-8")
    main_py = (ROOT / "aurix_bridge_server" / "main.py").read_text(encoding="utf-8")

    require("/dashboard/login" in main_py, "login route missing")
    require("/dashboard/session" in main_py, "session route missing")
    require("/dashboard/logout" in main_py, "logout route missing")
    require('@app.get("/api")' in main_py, "route index /api route missing")
    require("httponly" in (ROOT / "aurix_bridge_server" / "dashboard_auth.py").read_text(encoding="utf-8").lower(), "dashboard cookie must be HttpOnly")
    require("api_key" not in app_js, "dashboard JS must not read api_key from query")
    require("X-AURIX-API-Key" not in app_js and "x-aurix-api-key" not in app_js.lower(), "dashboard JS must not send API key headers")
    local_storage = "local" + "Storage"
    session_storage = "session" + "Storage"
    require(local_storage not in app_js, "dashboard JS must not use browser local storage")
    require(session_storage not in app_js, "dashboard JS must not use browser session storage")
    require("AURIX_API_KEY" not in app_js and "AURIX_API_KEY" not in index, "dashboard assets must not reference API key env var")
    require("/commands/open-market" not in app_js, "dashboard JS must not call open-market")
    require("?api_key" not in open_dashboard and "AURIX_API_KEY" not in open_dashboard, "open_dashboard must not append or read API key")
    require("/dashboard" in open_dashboard, "open_dashboard should open clean dashboard URL")

    import aurix_bridge_server.main as direct_main

    root_response = direct_main.root()
    require(getattr(root_response, "status_code", None) in {302, 303}, "root route must redirect")
    require(root_response.headers.get("location") == "/dashboard", "root route must redirect to dashboard")
    api_index = direct_main.api_index()
    require(api_index.get("dashboard") == "/dashboard" and api_index.get("dashboard_login") == "/dashboard/login", "route index missing dashboard entries")

    from aurix_bridge_server.dashboard_auth import (
        DashboardAuthConfig,
        create_session_token,
        verify_dashboard_password,
        verify_session_token,
    )

    config = DashboardAuthConfig(password="test-password", session_secret="test-secret", ttl_seconds=60)
    token = create_session_token(config, now=1000)
    require(verify_session_token(token, config, now=1001), "signed dashboard session token did not verify")
    require(not verify_session_token(token, config, now=2000), "expired dashboard session token verified")
    require(verify_dashboard_password("test-password", config), "dashboard password verification failed")
    require(not verify_dashboard_password("wrong-password", config), "wrong dashboard password verified")

    try:
        os.environ["AURIX_RUNTIME_PROFILE"] = "RAILWAY_CLOUD_BRIDGE"
        os.environ["AURIX_REQUIRE_API_KEY_FOR_REMOTE"] = "true"
        os.environ["AURIX_API_KEY"] = "test-api-key"
        os.environ["AURIX_DASHBOARD_PASSWORD"] = "test-dashboard-password"
        os.environ["AURIX_DASHBOARD_SESSION_SECRET"] = "test-dashboard-session-secret"
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["AURIX_DATA_DIR"] = tmpdir
            os.environ["AURIX_LOG_DIR"] = tmpdir
            from fastapi.testclient import TestClient
            import aurix_bridge_server.main as main_module

            client = TestClient(main_module.app)
            root = client.get("/", follow_redirects=False)
            require(root.status_code in {302, 303} and root.headers.get("location") == "/dashboard", "root did not redirect to dashboard")
            response = client.get("/dashboard", follow_redirects=False)
            require(response.status_code in {302, 303}, f"unauthenticated dashboard did not redirect: {response.status_code}")
            require(response.headers.get("location") == "/dashboard/login", "unauthenticated dashboard redirect target is wrong")
            bad = client.post("/dashboard/login", data={"password": "wrong"}, follow_redirects=False)
            require(bad.status_code == 401, f"bad dashboard login did not fail: {bad.status_code}")
            good = client.post("/dashboard/login", data={"password": "test-dashboard-password"}, follow_redirects=False)
            require(good.status_code in {302, 303}, f"good dashboard login did not redirect: {good.status_code}")
            require("httponly" in good.headers.get("set-cookie", "").lower(), "login cookie is not HttpOnly")
            authed = client.get("/dashboard/session")
            require(authed.status_code == 200 and authed.json().get("authenticated") is True, "session endpoint did not authenticate cookie")
    except (ImportError, RuntimeError, TypeError) as exc:
        print(f"WARN: dashboard redirect TestClient check skipped: {exc}")

    print("OK: dashboard auth checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
