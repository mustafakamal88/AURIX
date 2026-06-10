from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from aurix_common import write_json_atomic, write_text_atomic


UNKNOWN = "unknown"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _unknown_if_missing(value: Any) -> Any:
    return UNKNOWN if value is None or value == "" else value


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return UNKNOWN


def _rejection_messages(items: Any) -> list[str]:
    messages: list[str] = []
    for item in _list(items):
        if isinstance(item, dict):
            messages.append(str(item.get("message") or item.get("code") or item))
        elif item:
            messages.append(str(item))
    return messages


class TradeExplanationStore:
    def __init__(self, data_dir: str | Path = "data"):
        self.data_dir = Path(data_dir)
        self.explanations_dir = self.data_dir / "trade_explanations"
        self.explanations_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.explanations_dir / "index.json"
        self.history_file = self.explanations_dir / "history.jsonl"
        if not self.index_file.exists():
            write_json_atomic(self.index_file, [])
        self.history_file.touch(exist_ok=True)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def load_index(self) -> list[dict[str, Any]]:
        value = self._read_json(self.index_file, [])
        return value if isinstance(value, list) else []

    def latest(self) -> dict[str, Any]:
        items = self.load_index()
        return items[-1] if items else {}

    def write(self, explanation: dict[str, Any]) -> dict[str, Any]:
        trade_id = str(explanation.get("trade_id") or explanation.get("mt5_order_id") or explanation.get("id") or uuid4().hex)
        explanation = {**explanation, "trade_id": trade_id, "updated_at": utc_now_iso()}
        target = self.explanations_dir / f"{trade_id}.json"
        write_json_atomic(target, explanation)
        index = [item for item in self.load_index() if item.get("trade_id") != trade_id]
        index.append(
            {
                "trade_id": trade_id,
                "mt5_order_id": explanation.get("mt5_order_id"),
                "created_at": explanation.get("created_at"),
                "updated_at": explanation.get("updated_at"),
                "symbol": explanation.get("symbol"),
                "direction": explanation.get("direction"),
                "strategy_name": explanation.get("strategy_name"),
                "reason_summary": explanation.get("reason_summary"),
                "result": explanation.get("result"),
            }
        )
        write_json_atomic(self.index_file, index[-500:])
        rows = self._read_history()
        rows.append({"written_at": utc_now_iso(), "trade_id": trade_id, "path": str(target)})
        write_text_atomic(self.history_file, "".join(json.dumps(row, default=str) + "\n" for row in rows[-500:]))
        return explanation

    def _read_history(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines() if self.history_file.exists() else []:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows


def build_trade_explanation(
    *,
    oms_request: dict[str, Any] | None = None,
    oms_intent: dict[str, Any] | None = None,
    preview: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
    decision: dict[str, Any] | None = None,
    strategy_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = _dict(oms_request)
    intent = _dict(oms_intent)
    preview = _dict(preview)
    validation = _dict(validation)
    payload = _dict(payload)
    snapshot = _dict(snapshot)
    decision = _dict(decision)
    diagnostics = _dict(strategy_diagnostics)
    trace = _dict(_first(intent.get("decision_trace"), diagnostics.get("decision_trace"), {}))
    rule_checks = _dict(trace.get("rule_checks"))
    tick = _dict(snapshot.get("tick"))
    account = _dict(snapshot.get("account"))
    reasons = _list(intent.get("reasons")) or _list(diagnostics.get("reasons"))
    setup_reason = _first(intent.get("setup_reason"), decision.get("setup_reason"), diagnostics.get("setup_reason"))
    rejection_messages = _rejection_messages(validation.get("rejection_reasons"))
    reason_summary = setup_reason if setup_reason != UNKNOWN else (", ".join(rejection_messages) if rejection_messages else UNKNOWN)
    direction = _first(preview.get("direction"), request.get("direction"), intent.get("direction"), payload.get("side"))
    action = "TRADE_SHORT" if direction == "SELL" else "TRADE_LONG" if direction == "BUY" else _first(decision.get("action"))

    setup_components = {
        "reason": reason_summary,
        "reasons": reasons if reasons else UNKNOWN,
        "decision_trace_available": bool(trace),
        "rule_checks": rule_checks if rule_checks else UNKNOWN,
        "validation_rejections": rejection_messages if rejection_messages else UNKNOWN,
        "validation_status": _first(validation.get("status"), preview.get("validation_status")),
    }

    return {
        "id": uuid4().hex,
        "created_at": utc_now_iso(),
        "trade_id": _first(payload.get("id"), preview.get("id"), request.get("id"), intent.get("id")),
        "mt5_order_id": _first(payload.get("broker_order_id")),
        "symbol": _first(preview.get("symbol"), request.get("symbol"), intent.get("symbol"), tick.get("symbol")),
        "direction": direction,
        "volume": _first(preview.get("volume"), request.get("volume"), intent.get("volume"), payload.get("volume")),
        "entry": _first(preview.get("entry_reference"), request.get("entry_reference"), intent.get("entry_reference")),
        "stop_loss": _first(preview.get("stop_loss"), request.get("stop_loss"), intent.get("stop_loss"), payload.get("sl")),
        "take_profit": _first(preview.get("take_profit"), request.get("take_profit"), intent.get("take_profit"), payload.get("tp")),
        "opened_at": UNKNOWN,
        "closed_at": UNKNOWN,
        "result": _first(payload.get("status"), preview.get("status"), request.get("status")),
        "strategy_name": _first(preview.get("strategy_name"), request.get("strategy_name"), intent.get("strategy_name"), diagnostics.get("strategy_name")),
        "strategy_family": _first(diagnostics.get("strategy_family"), intent.get("strategy_name")),
        "action": action,
        "confidence": _first(intent.get("confidence"), decision.get("confidence"), diagnostics.get("confidence")),
        "score": _first(decision.get("score")),
        "session": _first(_dict(snapshot.get("context")).get("session_name"), decision.get("session")),
        "spread_at_decision": _first(validation.get("spread_points"), tick.get("spread_points")),
        "market_snapshot_time": _first(snapshot.get("received_at"), tick.get("time")),
        "signal_time": _first(intent.get("created_at")),
        "decision_time": _first(decision.get("generated_at"), decision.get("created_at")),
        "command_queued_time": _first(payload.get("queued_at")),
        "broker_result_time": UNKNOWN,
        "reason_summary": reason_summary,
        "setup_components": setup_components,
        "trace_setup": {
            "trap_detected": _unknown_if_missing(rule_checks.get("trap_detected")),
            "reclaim_detected": _unknown_if_missing(rule_checks.get("reclaim_detected")),
            "accept_detected": _unknown_if_missing(rule_checks.get("accept_detected")),
            "continuation_detected": _unknown_if_missing(rule_checks.get("continuation_detected")),
            "execute_triggered": _unknown_if_missing(rule_checks.get("execute_triggered")),
            "value_area_high": _first(trace.get("value_area_high")),
            "value_area_low": _first(trace.get("value_area_low")),
            "poc": _first(trace.get("poc")),
            "stop_reference": _first(intent.get("stop_loss"), request.get("stop_loss"), preview.get("stop_loss")),
            "target_reference": _first(intent.get("take_profit"), request.get("take_profit"), preview.get("take_profit")),
            "why_sell": reason_summary if direction == "SELL" else UNKNOWN,
            "invalidation_reason": _first(intent.get("invalidation_reason"), diagnostics.get("invalidation_reason")),
        },
        "evidence": {
            "oms_intent_id": intent.get("id"),
            "oms_request_id": request.get("id"),
            "command_preview_id": preview.get("id"),
            "command_payload_id": payload.get("id"),
            "source_signal_id": _first(preview.get("source_signal_id"), request.get("source_signal_id"), intent.get("source_signal_id")),
            "source_signal_event_id": _first(preview.get("source_signal_event_id"), request.get("source_signal_event_id"), intent.get("source_signal_event_id")),
            "strategy_diagnostics_snapshot": diagnostics if diagnostics else UNKNOWN,
            "decision_engine_result": decision if decision else UNKNOWN,
            "spread_risk_broker_gates": validation if validation else UNKNOWN,
            "account_currency": _first(account.get("currency"), validation.get("account_currency")),
        },
        "safety": {
            "explanation_only": True,
            "mt5_commands_queued": False,
            "broker_order_created": False,
            "paper_trade_created": False,
            "ea_settings_modified": False,
        },
    }
