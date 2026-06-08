from __future__ import annotations

import tempfile
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from aurix_bridge_server.models import Command, ExecutionResult
from aurix_bridge_server.store import JsonStore


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        store = JsonStore(tmpdir)

        expired = Command(
            type="OPEN_MARKET",
            symbol="XAUUSDm",
            direction="BUY",
            volume=0.01,
            created_at=(datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(),
        )
        store.add_command(expired)
        assert_equal(store.next_command_for_terminal("AURIX-MAC-001"), None, "expired command dispatch")
        assert_equal(store.get_command(expired.id)["status"], "EXPIRED", "expired command status")

        queued = Command(type="OPEN_MARKET", symbol="XAUUSDm", direction="BUY", volume=0.01)
        store.add_command(queued)
        dispatched = store.next_command_for_terminal("AURIX-MAC-001")
        assert dispatched is not None
        assert_equal(dispatched.id, queued.id, "dispatched command id")
        queued_state = store.get_command(queued.id)
        assert_equal(queued_state["status"], "DISPATCHED", "dispatch status")
        assert_equal(queued_state["dispatch_count"], 1, "dispatch count")
        assert_equal(store.next_command_for_terminal("AURIX-MAC-001"), None, "duplicate dispatch")

        result = ExecutionResult(
            terminal_id="AURIX-MAC-001",
            command_id=queued.id,
            ok=False,
            retcode=-1,
            message="Live trading blocked by EA safety gate",
            symbol="XAUUSDm",
            direction="BUY",
            volume=0.01,
        )
        store.mark_result(result)
        assert_equal(store.get_command(queued.id)["status"], "EXECUTION_BLOCKED", "blocked result status")

        cancel_me = Command(type="OPEN_MARKET", symbol="XAUUSDm", direction="BUY", volume=0.01)
        store.add_command(cancel_me)
        assert_equal(store.cancel_command(cancel_me.id), True, "cancel queued")
        assert_equal(store.get_command(cancel_me.id)["status"], "CANCELLED", "cancelled status")
        assert_equal(store.next_command_for_terminal("AURIX-MAC-001"), None, "cancelled not dispatched")

    print("OK: lifecycle self-checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
