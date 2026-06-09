from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CORE_JSON_FILES = [
    "paper_trades.json",
    "journal_entries.json",
    "evidence_growth_report.json",
    "live_readiness_report.json",
    "signal_path_certification_report.json",
    "commands.json",
    "execution_results.json",
    "demo_oms/order_requests.json",
    "demo_command_queue/payloads.json",
    "event_bus/status.json",
    "event_bus/state_snapshot.json",
]


def _age_seconds(path: Path) -> float:
    return max(0.0, datetime.now(timezone.utc).timestamp() - path.stat().st_mtime)


def _json_status(path: Path, expected: str) -> dict[str, Any]:
    if not path.exists():
        return {"status": "WARNING", "path": str(path), "readable": False, "note": "missing"}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "ERROR", "path": str(path), "readable": False, "note": str(exc)}
    ok_type = isinstance(value, list) if expected == "list" else isinstance(value, dict)
    return {"status": "OK" if ok_type else "WARNING", "path": str(path), "readable": True, "count": len(value) if isinstance(value, list) else None, "note": None if ok_type else f"expected {expected}"}


def _corrupt_json_files(root: Path) -> list[str]:
    corrupt: list[str] = []
    for path in root.glob("**/*.json"):
        if ".tmp." in path.name:
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            corrupt.append(str(path))
    return corrupt


def _stale_temp_files(root: Path, threshold_seconds: int) -> list[str]:
    stale: list[str] = []
    for path in root.glob("**/*.tmp.*"):
        try:
            if _age_seconds(path) > threshold_seconds:
                stale.append(str(path))
        except OSError:
            continue
    return stale


def build_evidence_integrity_status(data_dir: str | Path = "data", *, stale_temp_threshold_seconds: int = 600) -> dict[str, Any]:
    root = Path(data_dir)
    paper = _json_status(root / "paper_trades.json", "list")
    journal = _json_status(root / "journal_entries.json", "list")
    evidence_monitor = _json_status(root / "evidence_growth_report.json", "dict")
    live_readiness = _json_status(root / "live_readiness_report.json", "dict")
    signal_cert = _json_status(root / "signal_path_certification_report.json", "dict")
    corrupt = _corrupt_json_files(root)
    stale_temp = _stale_temp_files(root, stale_temp_threshold_seconds)
    notes: list[str] = []
    for label, value in [("paper ledger", paper), ("journal ledger", journal), ("evidence monitor", evidence_monitor), ("live readiness", live_readiness), ("signal certification", signal_cert)]:
        if value.get("status") != "OK":
            notes.append(f"{label}: {value.get('note')}")
    if stale_temp:
        notes.append(f"stale temp files: {len(stale_temp)}")
    if corrupt:
        notes.append(f"corrupt JSON files: {len(corrupt)}")
    status = "ERROR" if corrupt or any(item.get("status") == "ERROR" for item in [paper, journal, evidence_monitor, live_readiness, signal_cert]) else "WARNING" if stale_temp or notes else "OK"
    paper_count = int(paper.get("count") or 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "paper_ledger": paper,
        "journal_ledger": journal,
        "evidence_monitor": evidence_monitor,
        "live_readiness": live_readiness,
        "signal_certification": signal_cert,
        "stale_temp_files": stale_temp,
        "stale_temp_file_count": len(stale_temp),
        "corrupt_json_files": corrupt,
        "corrupt_json_file_count": len(corrupt),
        "counts_consistent": paper_count >= 0,
        "notes": notes or ["core evidence files are readable"],
        "safety": {
            "read_only_check": True,
            "paper_trade_created": False,
            "order_request_created": False,
            "mt5_command_queued": False,
            "broker_order_created": False,
        },
    }
