from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from aurix_common import write_json_atomic, write_text_atomic
from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType, EventSafety

from .config import StrategyAgentsConfig
from .diagnostics import build_strategy_pipeline_snapshot, result_state, write_strategy_pipeline_snapshot
from .models import StrategyAgentSafety, StrategyEvaluationInput, StrategyEvaluationResult, utc_now_iso
from .registry import StrategyAgentRegistry


class StrategyAgentStore:
    def __init__(self, data_dir: Union[str, Path] = "data", config: Optional[StrategyAgentsConfig] = None):
        self.data_dir = Path(data_dir)
        self.config = config
        self.store_dir = self.data_dir / "strategy_agents"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.store_dir / "status.json"
        self.latest_file = self.store_dir / "latest_evaluations.json"
        self.history_file = self.store_dir / "history.jsonl"
        if not self.latest_file.exists():
            self._write_json_atomic(self.latest_file, [])

    def _write_json_atomic(self, path: Path, value: Any) -> None:
        write_json_atomic(path, value)

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def latest(self) -> list[dict[str, Any]]:
        data = self._read_json(self.latest_file, [])
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def history(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        if not self.history_file.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows[-limit:] if limit else rows

    def save_results(self, results: list[StrategyEvaluationResult], registry: StrategyAgentRegistry) -> None:
        rows = [result.model_dump() for result in results]
        self._write_json_atomic(self.latest_file, rows)
        existing = self.history()
        existing.extend(rows)
        existing = existing[-1000:]
        write_text_atomic(self.history_file, "".join(json.dumps(item, default=str) + "\n" for item in existing))
        status = self.status(registry)
        self._write_json_atomic(self.status_file, status)
        write_strategy_pipeline_snapshot(
            self.data_dir,
            build_strategy_pipeline_snapshot(
                data_dir=self.data_dir,
                registry_status=status,
                latest_evaluations=rows,
                fast_rsi_state=self._read_json(self.store_dir / "fast_rsi_first_reversal_state.json", {}),
            ),
        )

    def status(self, registry: StrategyAgentRegistry) -> dict[str, Any]:
        latest = self.latest()
        counts: dict[str, int] = {}
        for item in latest:
            status = str(item.get("status") or "UNKNOWN")
            counts[status] = counts.get(status, 0) + 1
        last_at = max([str(item.get("generated_at")) for item in latest if item.get("generated_at")] or [None])
        data = registry.get_registry_status(counts, last_at).model_dump()
        self._write_json_atomic(self.status_file, data)
        return data

    def reset(self, registry: StrategyAgentRegistry) -> dict[str, Any]:
        self._write_json_atomic(self.latest_file, [])
        self.history_file.write_text("", encoding="utf-8")
        status = registry.get_registry_status({}, None).model_dump()
        self._write_json_atomic(self.status_file, status)
        return status


class StrategyAgentEvaluator:
    def __init__(
        self,
        *,
        data_dir: Union[str, Path],
        config: StrategyAgentsConfig,
        registry: StrategyAgentRegistry,
        event_bus: Optional[AurixEventBus] = None,
        latest_signals: Any = None,
        candles: Any = None,
        context: Any = None,
    ):
        self.data_dir = Path(data_dir)
        self.config = config
        self.registry = registry
        self.event_bus = event_bus
        self.store = StrategyAgentStore(data_dir, config)
        self.latest_signals = latest_signals or (lambda: [])
        self.candles = candles or (lambda: [])
        self.context = context or (lambda: None)

    def _runtime_state(self) -> dict[str, Any]:
        if self.event_bus is None:
            return {}
        try:
            return self.event_bus.get_latest_state()
        except Exception:
            return {}

    def _latest_for_source(self, source_strategy: Optional[str]) -> Optional[dict[str, Any]]:
        signals = self.latest_signals()
        matches = [item for item in signals if isinstance(item, dict) and item.get("strategy_name") == source_strategy]
        return matches[-1] if matches else None

    def _publish_diagnostic_event(self, event_type: AurixEventType, payload: dict[str, Any], *, correlation_id: str | None = None) -> Optional[str]:
        if not self.config.publish_to_event_bus or self.event_bus is None:
            return None
        event = self.event_bus.publish_event(
            AurixEvent(
                event_type=event_type,
                source="strategy_pipeline_diagnostics",
                symbol=str(payload.get("symbol") or self.config.symbol),
                correlation_id=correlation_id,
                payload=payload,
                safety=EventSafety(),
            )
        )
        return event.get("event_id")

    def evaluate_agent(self, agent_id: str) -> StrategyEvaluationResult:
        agent = self.registry.get_agent(agent_id)
        if agent is None:
            raise KeyError(f"Strategy agent not found: {agent_id}")
        if not agent.spec.enabled:
            return StrategyEvaluationResult(
                agent_id=agent.spec.id,
                strategy_name=agent.spec.name,
                strategy_version=agent.spec.version,
                symbol=agent.spec.symbol,
                mode=agent.spec.mode,
                status="SKIPPED",
                setup_reason="agent disabled",
            )
        source = self.registry.source_strategy(agent_id)
        correlation_id = uuid4().hex
        self._publish_diagnostic_event(
            AurixEventType.STRATEGY_EVALUATION_STARTED,
            {"diagnostic_event": "strategy_evaluation_started", "agent_id": agent_id, "strategy_name": agent.spec.name, "symbol": self.config.symbol},
            correlation_id=correlation_id,
        )
        try:
            result = agent.evaluate(
                StrategyEvaluationInput(
                    agent_id=agent_id,
                    symbol=self.config.symbol,
                    runtime_state=self._runtime_state(),
                    latest_signal=self._latest_for_source(source),
                    candles=self.candles(),
                    context=self.context(),
                )
            )
        except Exception as exc:
            self._publish_diagnostic_event(
                AurixEventType.STRATEGY_PIPELINE_ERROR,
                {"diagnostic_event": "strategy_pipeline_error", "agent_id": agent_id, "strategy_name": agent.spec.name, "error": str(exc)},
                correlation_id=correlation_id,
            )
            raise
        result.safety = StrategyAgentSafety()
        result.correlation_id = result.correlation_id or correlation_id
        result.event_id = self._publish_events(result)
        state = result_state(result.model_dump())
        self._publish_diagnostic_event(
            AurixEventType.STRATEGY_EVALUATION_COMPLETED,
            {"diagnostic_event": "strategy_evaluation_completed", "agent_id": agent_id, "strategy_name": result.strategy_name, "result": state, "status": result.status},
            correlation_id=result.correlation_id,
        )
        if state == "ACTIONABLE":
            diagnostic_type = AurixEventType.STRATEGY_SIGNAL_ACTIONABLE
            diagnostic_name = "strategy_signal_actionable"
        elif state == "LOW_CONFIDENCE":
            diagnostic_type = AurixEventType.STRATEGY_SIGNAL_CANDIDATE
            diagnostic_name = "strategy_signal_candidate"
        else:
            diagnostic_type = AurixEventType.STRATEGY_SIGNAL_REJECTED
            diagnostic_name = "strategy_signal_rejected"
        self._publish_diagnostic_event(
            diagnostic_type,
            {
                "diagnostic_event": diagnostic_name,
                "agent_id": agent_id,
                "strategy_name": result.strategy_name,
                "result": state,
                "status": result.status,
                "direction": result.direction,
                "confidence": result.confidence,
                "rejection_reasons": [reason.model_dump() for reason in result.rejection_reasons],
            },
            correlation_id=result.correlation_id,
        )
        return result

    def evaluate_all_agents(self) -> list[StrategyEvaluationResult]:
        if not self.config.enabled:
            return []
        self._publish_diagnostic_event(
            AurixEventType.STRATEGY_REGISTRY_LOADED,
            {
                "diagnostic_event": "strategy_registry_loaded",
                "registered_count": len(self.registry.list_registered_agents()),
                "enabled_count": len(self.registry.get_enabled_agents()),
            },
        )
        results = [self.evaluate_agent(agent.spec.id) for agent in self.registry.get_enabled_agents()]
        self.store.save_results(results, self.registry)
        return results

    def _publish_events(self, result: StrategyEvaluationResult) -> Optional[str]:
        if not self.config.publish_to_event_bus or self.event_bus is None:
            return None
        evaluation_payload = {
            "agent_id": result.agent_id,
            "strategy_name": result.strategy_name,
            "strategy_version": result.strategy_version,
            "symbol": result.symbol,
            "status": result.status,
            "direction": result.direction,
            "confidence": result.confidence,
            "setup_reason": result.setup_reason,
            "rejection_reasons": [reason.model_dump() for reason in result.rejection_reasons],
            "decision_trace_available": bool(result.decision_trace),
            "command_id": None,
        }
        evaluation_event = self.event_bus.publish_event(
            AurixEvent(
                event_type=AurixEventType.STRATEGY_EVALUATION_EVENT,
                source="strategy_agent_evaluator",
                symbol=result.symbol,
                correlation_id=result.correlation_id,
                payload=evaluation_payload,
                safety=EventSafety(),
            )
        )
        if result.status == "SIGNAL":
            self.event_bus.publish_event(
                AurixEvent(
                    event_type=AurixEventType.SIGNAL_EVENT,
                    source="strategy_agent_evaluator",
                    symbol=result.symbol,
                    correlation_id=result.correlation_id,
                    causation_id=evaluation_event.get("event_id"),
                    payload={
                        "signal_id": result.id,
                        "agent_id": result.agent_id,
                        "strategy_name": result.strategy_name,
                        "strategy_version": result.strategy_version,
                        "symbol": result.symbol,
                        "direction": result.direction,
                        "status": result.status,
                        "confidence": result.confidence,
                        "entry_reference": result.entry_reference,
                        "stop_loss_reference": result.stop_loss_reference,
                        "take_profit_reference": result.take_profit_reference,
                        "setup_reason": result.setup_reason,
                        "decision_trace": result.decision_trace,
                        "command_id": None,
                    },
                    safety=EventSafety(),
                )
            )
        return evaluation_event.get("event_id")

    def status(self) -> dict[str, Any]:
        status = self.store.status(self.registry)
        safety = status.get("safety") or {}
        latest = self.latest()
        latest_signal = next((item for item in reversed(latest) if item.get("status") == "SIGNAL"), None)
        latest_fast_rsi = next((item for item in reversed(latest) if item.get("agent_id") == "fast_rsi_first_reversal_v1"), None)
        status.update(
            {
                "paper_trade_creation_allowed": safety.get("paper_trade_creation_allowed", False),
                "order_request_creation_allowed": safety.get("order_request_creation_allowed", False),
                "live_execution_allowed": safety.get("live_execution_allowed", False),
                "command_queueing_allowed": safety.get("command_queueing_allowed", False),
                "latest_signal": latest_signal,
                "latest_fast_rsi": latest_fast_rsi,
            }
        )
        return status

    def registry_payload(self) -> dict[str, Any]:
        return {"agents": [agent.model_dump() for agent in self.registry.list_registered_agents()]}

    def latest(self) -> list[dict[str, Any]]:
        return self.store.latest()

    def history(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        return self.store.history(limit)

    def reset(self) -> dict[str, Any]:
        return self.store.reset(self.registry)
