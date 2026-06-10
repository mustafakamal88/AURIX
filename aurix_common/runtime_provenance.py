from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deployment_commit(default: str = "unknown") -> str:
    for key in ("RAILWAY_GIT_COMMIT_SHA", "GIT_COMMIT_SHA", "SOURCE_VERSION"):
        value = os.getenv(key)
        if value:
            return str(value)
    return default


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def _list_count(path: Path) -> int:
    value = _read_json(path, [])
    return len(value) if isinstance(value, list) else 0


def collect_runtime_counters(data_dir: str | Path = "data") -> dict[str, int]:
    root = Path(data_dir)
    snapshot = _read_json(root / "latest_snapshot.json", {})
    positions = snapshot.get("positions") if isinstance(snapshot, dict) else []
    orders = snapshot.get("orders") if isinstance(snapshot, dict) else []
    return {
        "paper_trades": _list_count(root / "paper_trades.json"),
        "order_requests": _list_count(root / "demo_oms" / "order_requests.json"),
        "oms_requests": _list_count(root / "demo_oms" / "order_requests.json"),
        "commands": _list_count(root / "commands.json"),
        "mt5_commands_queued": len([cmd for cmd in (_read_json(root / "commands.json", []) or []) if isinstance(cmd, dict) and cmd.get("status") in {"QUEUED", "DISPATCHED"}]),
        "execution_results": _list_count(root / "execution_results.json"),
        "broker_positions": len(positions) if isinstance(positions, list) else 0,
        "broker_orders": len(orders) if isinstance(orders, list) else 0,
        "event_bus_events": _read_jsonl_count(root / "event_bus" / "events.jsonl"),
    }


class RuntimeSession:
    def __init__(self, *, data_dir: str | Path = "data", mode: str = "DECISION_ONLY", symbol: str = "XAUUSDm"):
        self.data_dir = Path(data_dir)
        self.runtime_session_id = uuid4().hex
        self.process_id = os.getpid()
        self.started_at = utc_now_iso()
        self.mode = mode
        self.symbol = symbol
        self.baseline_counters = collect_runtime_counters(self.data_dir)

    def _uptime_seconds(self) -> float:
        return max(0.0, (datetime.now(timezone.utc) - _parse_time(self.started_at)).total_seconds())

    def current_counters(self) -> dict[str, int]:
        return collect_runtime_counters(self.data_dir)

    def session_deltas(self) -> dict[str, int]:
        current = self.current_counters()
        return {key: int(current.get(key, 0)) - int(self.baseline_counters.get(key, 0)) for key in sorted(set(current) | set(self.baseline_counters))}

    def safety_assertion(self) -> dict[str, Any]:
        deltas = self.session_deltas()
        created_paper_trade = deltas.get("paper_trades", 0) > 0
        created_order_request = deltas.get("order_requests", 0) > 0
        queued_mt5_command = deltas.get("commands", 0) > 0 or deltas.get("mt5_commands_queued", 0) > 0
        created_demo_oms_request = deltas.get("oms_requests", 0) > 0
        created_broker_order = deltas.get("broker_orders", 0) > 0
        modified_broker_order = False
        closed_broker_order = deltas.get("broker_orders", 0) < 0
        changed_ea_settings = "unknown"
        overall_safe = not any([created_paper_trade, created_order_request, queued_mt5_command, created_demo_oms_request, created_broker_order, modified_broker_order, closed_broker_order])
        return {
            "created_paper_trade": created_paper_trade,
            "created_order_request": created_order_request,
            "queued_mt5_command": queued_mt5_command,
            "created_demo_oms_request": created_demo_oms_request,
            "created_broker_order": created_broker_order,
            "modified_broker_order": modified_broker_order,
            "closed_broker_order": closed_broker_order,
            "changed_ea_settings": changed_ea_settings,
            "overall_safe": overall_safe,
        }

    def provenance_event(self) -> dict[str, Any]:
        return {
            "runtime_session_id": self.runtime_session_id,
            "deployment_commit": deployment_commit(),
            "component": "aurix_bridge_server",
            "created_at": self.started_at,
            "source_module": "aurix_common.runtime_provenance",
            "safety_mode": self.mode,
            "live_enabled": False,
            "command_queue_enabled": False,
        }

    def payload(self) -> dict[str, Any]:
        return {
            "runtime_session_id": self.runtime_session_id,
            "deployment_commit": deployment_commit(),
            "process_id": self.process_id,
            "started_at": self.started_at,
            "generated_at": utc_now_iso(),
            "uptime_seconds": round(self._uptime_seconds(), 3),
            "mode": self.mode,
            "symbol": self.symbol,
            "baseline_counters": self.baseline_counters,
            "lifetime_counters": self.current_counters(),
            "session_counters": self.session_deltas(),
            "safety_assertion": self.safety_assertion(),
            "latest_provenance_event": self.provenance_event(),
        }


def legacy_runtime_provenance(data_dir: str | Path = "data", *, mode: str = "UNKNOWN", symbol: str = "XAUUSDm") -> dict[str, Any]:
    counters = collect_runtime_counters(data_dir)
    return {
        "runtime_session_id": "legacy_unknown",
        "deployment_commit": "unknown",
        "process_id": os.getpid(),
        "started_at": None,
        "generated_at": utc_now_iso(),
        "uptime_seconds": None,
        "mode": mode,
        "symbol": symbol,
        "baseline_counters": counters,
        "lifetime_counters": counters,
        "session_counters": {key: 0 for key in counters},
        "safety_assertion": {
            "created_paper_trade": False,
            "created_order_request": False,
            "queued_mt5_command": False,
            "created_demo_oms_request": False,
            "created_broker_order": False,
            "modified_broker_order": False,
            "closed_broker_order": False,
            "changed_ea_settings": "unknown",
            "overall_safe": True,
        },
        "latest_provenance_event": {"runtime_session_id": "legacy_unknown", "deployment_commit": "unknown", "component": "legacy", "created_at": None},
    }
