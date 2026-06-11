from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_persistence import DurableAuditError, DurableAuditStore


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def count_rows(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"select count(*) from {table}").fetchone()[0])
    finally:
        conn.close()


def fetch_one(db_path: Path, sql: str) -> tuple:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchone()
    finally:
        conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aurix-durable-audit-") as tmpdir:
        db_path = Path(tmpdir) / "audit.sqlite"
        store = DurableAuditStore.sqlite_for_tests(db_path, tmpdir)
        status = store.status()
        require(status["durable_audit"] == "ENABLED" and status["database_connected"] is True, f"schema init failed: {status}")

        event_id = store.append_event({"event_type": "SIGNAL_EVENT", "symbol": "XAUUSDm", "payload": {"ok": True}})
        require(event_id and count_rows(db_path, "aurix_events") == 1, "append-only event write failed")
        event_row = fetch_one(db_path, "select runtime_session_id, deployment_commit from aurix_events")
        require(event_row == ("test-runtime", "test"), f"durable event provenance missing: {event_row}")

        explanation_id = store.write_trade_explanation(
            {
                "id": "explain-1",
                "symbol": "XAUUSDm",
                "direction": "SELL",
                "volume": 0.01,
                "entry": 4174.178,
                "stop_loss": 4192.438,
                "take_profit": 4162.438,
                "strategy_name": "TRACE",
                "strategy_family": "TRACE",
                "confidence": 0.8,
                "score": 0.9,
                "reason_summary": "trap + reclaim + accept + continuation",
                "setup_components": {"trap_detected": True},
                "result": "PENDING",
            },
            command_id="cmd-signal-1",
            decision_id="decision-1",
        )
        require(explanation_id == "explain-1" and count_rows(db_path, "trade_explanations") == 1, "trade explanation write failed")

        command = {"command_id": "cmd-signal-1", "action": "OPEN_MARKET", "symbol": "XAUUSDm", "side": "SELL", "volume": 0.01, "stop_loss": 4192.438, "take_profit": 4162.438}
        store.write_command_audit(command, explanation_id=explanation_id, decision_id="decision-1", queued=False)
        require(count_rows(db_path, "command_audit") == 1, "command audit write-before-send failed")
        store.mark_command_queued("cmd-signal-1", command)
        require(store.command_already_queued("cmd-signal-1") is True, "queued command audit not detected")
        store.write_command_audit(command, explanation_id=explanation_id, decision_id="decision-1", queued=False, status="RETRY_SEEN")
        require(count_rows(db_path, "command_audit") == 1, "duplicate command_id created duplicate audit row")

        queued_commands: list[dict[str, object]] = []
        failing = DurableAuditStore(data_dir=tmpdir, database_url="postgres://example", connect=lambda: (_ for _ in ()).throw(RuntimeError("write failed")))
        try:
            failing.write_command_audit({"command_id": "cmd-fail", "symbol": "XAUUSDm"})
            raise AssertionError("failing DB write did not raise")
        except DurableAuditError:
            pass
        require(queued_commands == [], "DB write failure must not queue MT5 commands")
        require(failing.status()["durable_audit"] == "DISABLED", f"failing DB did not safely disable audit: {failing.status()}")

        local_data = Path(tmpdir) / "local-data"
        local_store = DurableAuditStore.sqlite_local(local_data, runtime_session_id="local-runtime")
        local_status = local_store.status()
        local_db_path = local_data / "aurix_durable_audit.sqlite"
        require(local_db_path.exists(), f"local SQLite durable audit DB missing: {local_db_path}")
        require(local_status["durable_audit"] == "ENABLED" and local_status["database_connected"] is True, f"local SQLite durable audit not connected: {local_status}")
        require(local_status["source_of_truth"] == "local SQLite durable audit", f"local source of truth wrong: {local_status}")

    clean_env = os.environ.copy()
    clean_env.pop("DATABASE_URL", None)
    with tempfile.TemporaryDirectory(prefix="aurix-durable-audit-check-") as check_tmp:
        check_data_dir = str(Path(check_tmp) / "data")
        missing = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "check_railway_durable_audit.py"), "--data-dir", check_data_dir],
            cwd=PROJECT_ROOT,
            env=clean_env,
            text=True,
            capture_output=True,
            check=False,
        )
        require(missing.returncode == 0, f"missing local DATABASE_URL should exit 0: {missing.stdout} {missing.stderr}")
        require("DATABASE_URL present: False" in missing.stdout, f"missing DATABASE_URL report unclear: {missing.stdout}")
        require("local-only warning" in missing.stdout, f"missing DATABASE_URL warning absent: {missing.stdout}")

        required_missing = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "check_railway_durable_audit.py"), "--require-db", "--data-dir", check_data_dir],
            cwd=PROJECT_ROOT,
            env=clean_env,
            text=True,
            capture_output=True,
            check=False,
        )
        require(required_missing.returncode != 0, "--require-db should fail when DATABASE_URL is missing")

        secret_url = "postgresql://user:super-secret-password@127.0.0.1:1/db"
        secret_env = clean_env | {"DATABASE_URL": secret_url}
        redacted = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "check_railway_durable_audit.py"), "--data-dir", check_data_dir],
            cwd=PROJECT_ROOT,
            env=secret_env,
            text=True,
            capture_output=True,
            check=False,
        )
    combined = redacted.stdout + redacted.stderr
    require(redacted.returncode != 0, "invalid DATABASE_URL should fail connection/schema check")
    require(secret_url not in combined and "super-secret-password" not in combined, f"health-check leaked DATABASE_URL: {combined}")

    print("OK: durable audit self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
