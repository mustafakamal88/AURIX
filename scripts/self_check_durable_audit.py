from __future__ import annotations

import sqlite3
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aurix-durable-audit-") as tmpdir:
        db_path = Path(tmpdir) / "audit.sqlite"
        store = DurableAuditStore.sqlite_for_tests(db_path, tmpdir)
        status = store.status()
        require(status["durable_audit"] == "ENABLED" and status["database_connected"] is True, f"schema init failed: {status}")

        event_id = store.append_event({"event_type": "SIGNAL_EVENT", "symbol": "XAUUSDm", "payload": {"ok": True}})
        require(event_id and count_rows(db_path, "aurix_events") == 1, "append-only event write failed")

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
        require(failing.status()["durable_audit"] == "ERROR", f"failing DB did not set ERROR: {failing.status()}")

    print("OK: durable audit self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
