from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

from aurix_common import write_json_atomic, write_text_atomic
from aurix_event_bus import AurixEvent, AurixEventBus, AurixEventType, EventSafety

from .candle_context import build_closed_candle_context
from .candle_timeframe import normalize_candles_for_timeframe
from .config import StrategyAgentsConfig
from .diagnostics import build_strategy_pipeline_snapshot, result_state, write_strategy_pipeline_snapshot
from .models import StrategyAgentSafety, StrategyEvaluationInput, StrategyEvaluationResult, StrategyRejectionReason, utc_now_iso
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
        self.trace_file = self.store_dir / "trace.jsonl"
        self.latest_trace_file = self.store_dir / "latest_trace.json"
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

    def recent_traces(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        if not self.trace_file.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.trace_file.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows[-limit:] if limit else rows

    def latest_trace(self) -> dict[str, Any]:
        return self._read_json(self.latest_trace_file, {})

    def save_trace(self, trace: dict[str, Any]) -> None:
        self._write_json_atomic(self.latest_trace_file, trace)
        rows = self.recent_traces()
        rows.append(trace)
        rows = rows[-1000:]
        write_text_atomic(self.trace_file, "".join(json.dumps(item, default=str) + "\n" for item in rows))

    def update_latest_trace_decision(self, updates: dict[str, Any]) -> dict[str, Any]:
        trace = self.latest_trace()
        if not trace:
            return {}
        trace.update(updates)
        self.save_trace(trace)
        status = self._read_json(self.status_file, {})
        if isinstance(status, dict):
            status.update(
                {
                    "last_decision_trace": trace,
                    "selected_candidate": trace.get("selected_candidate"),
                    "last_block_reason": trace.get("block_reason"),
                    "latest_closed_candle_timestamp": trace.get("latest_closed_candle_timestamp"),
                    "latest_raw_candle_timestamp": trace.get("latest_raw_candle_timestamp"),
                    "latest_strategy_closed_candle_timestamp": trace.get("latest_strategy_closed_candle_timestamp"),
                    "available_closed_candle_count": trace.get("available_candle_count"),
                    "raw_timeframe": trace.get("raw_timeframe"),
                    "strategy_timeframe": trace.get("strategy_timeframe"),
                    "resampled": trace.get("resampled"),
                    "source_candle_count": trace.get("source_candle_count"),
                    "raw_closed_candle_count": trace.get("raw_closed_candle_count"),
                    "m15_bucket_count_total": trace.get("m15_bucket_count_total"),
                    "m15_bucket_count_complete": trace.get("m15_bucket_count_complete"),
                    "m15_bucket_count_incomplete": trace.get("m15_bucket_count_incomplete"),
                    "strategy_candle_count": trace.get("strategy_candle_count"),
                    "required_strategy_candle_count": trace.get("required_strategy_candle_count"),
                    "dropped_latest_incomplete_bucket": trace.get("dropped_latest_incomplete_bucket"),
                    "last_incomplete_bucket_start": trace.get("last_incomplete_bucket_start"),
                    "candle_memory_status": trace.get("candle_memory_status"),
                    "last_strategy_outputs": trace.get("strategy_outputs") or [],
                }
            )
            self._write_json_atomic(self.status_file, status)
        return trace

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
        data["evaluations_this_session"] = len(self.history())
        trace = self.latest_trace()
        if trace:
            data.update(
                {
                    "last_decision_trace": trace,
                    "selected_candidate": trace.get("selected_candidate"),
                    "last_block_reason": trace.get("block_reason"),
                    "latest_closed_candle_timestamp": trace.get("latest_closed_candle_timestamp"),
                    "latest_raw_candle_timestamp": trace.get("latest_raw_candle_timestamp"),
                    "latest_strategy_closed_candle_timestamp": trace.get("latest_strategy_closed_candle_timestamp"),
                    "available_closed_candle_count": trace.get("available_candle_count"),
                    "raw_timeframe": trace.get("raw_timeframe"),
                    "strategy_timeframe": trace.get("strategy_timeframe"),
                    "resampled": trace.get("resampled"),
                    "source_candle_count": trace.get("source_candle_count"),
                    "raw_closed_candle_count": trace.get("raw_closed_candle_count"),
                    "m15_bucket_count_total": trace.get("m15_bucket_count_total"),
                    "m15_bucket_count_complete": trace.get("m15_bucket_count_complete"),
                    "m15_bucket_count_incomplete": trace.get("m15_bucket_count_incomplete"),
                    "strategy_candle_count": trace.get("strategy_candle_count"),
                    "required_strategy_candle_count": trace.get("required_strategy_candle_count"),
                    "dropped_latest_incomplete_bucket": trace.get("dropped_latest_incomplete_bucket"),
                    "last_incomplete_bucket_start": trace.get("last_incomplete_bucket_start"),
                    "candle_memory_status": trace.get("candle_memory_status"),
                    "last_strategy_outputs": trace.get("strategy_outputs") or [],
                }
            )
        self._write_json_atomic(self.status_file, data)
        return data

    def reset(self, registry: StrategyAgentRegistry) -> dict[str, Any]:
        self._write_json_atomic(self.latest_file, [])
        self.history_file.write_text("", encoding="utf-8")
        self.trace_file.write_text("", encoding="utf-8")
        self._write_json_atomic(self.latest_trace_file, {})
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

    def build_candle_context(self) -> dict[str, Any]:
        strategy_timeframe = "M15"
        normalized = normalize_candles_for_timeframe(self.candles(), strategy_timeframe=strategy_timeframe)
        return build_closed_candle_context(
            normalized.get("candles") or [],
            symbol=self.config.symbol,
            timeframe=strategy_timeframe,
            metadata=normalized,
        )

    def _input_context(self, shared_context: dict[str, Any]) -> dict[str, Any]:
        external = self.context()
        base = external if isinstance(external, dict) else {}
        return {**base, "shared_candle_context": shared_context}

    def _context_guard_result(self, agent_id: str, shared_context: dict[str, Any]) -> StrategyEvaluationResult | None:
        available = int(shared_context.get("strategy_candle_count") or shared_context.get("available_candle_count") or 0)
        required = int(shared_context.get("required_strategy_candle_count") or 26)
        if available >= required:
            return None
        agent = self.registry.get_agent(agent_id)
        if agent is None:
            return None
        reason = str(shared_context.get("insufficient_reason") or "insufficient_candle_memory")
        return StrategyEvaluationResult(
            agent_id=agent.spec.id,
            strategy_name=self.registry.source_strategy(agent_id) or agent.spec.name,
            strategy_version=agent.spec.version,
            symbol=agent.spec.symbol,
            mode=agent.spec.mode,
            status="SKIPPED",
            direction=None,
            confidence=0.0,
            setup_reason=reason,
            decision_trace={"shared_candle_context": shared_context, "rule_checks": {"enough_candle_memory": False}},
            rejection_reasons=[
                StrategyRejectionReason(
                    code=reason,
                    message=f"Need at least {required} closed strategy-timeframe candles: one trigger candle plus 25 prior context candles.",
                )
            ],
            safety=StrategyAgentSafety(),
        )

    def _augment_result_with_context(self, result: StrategyEvaluationResult, shared_context: dict[str, Any]) -> StrategyEvaluationResult:
        trace = result.decision_trace if isinstance(result.decision_trace, dict) else {}
        trace["shared_candle_context"] = shared_context
        trace["normalized_output"] = self.normalize_output(result.model_dump(), shared_context)
        result.decision_trace = trace
        return result

    def normalize_output(self, result: dict[str, Any], shared_context: dict[str, Any]) -> dict[str, Any]:
        direction_raw = result.get("direction")
        action = "WAIT"
        direction = "NONE"
        if result.get("status") == "SIGNAL" and direction_raw == "BUY":
            action = "TRADE_LONG"
            direction = "LONG"
        elif result.get("status") == "SIGNAL" and direction_raw == "SELL":
            action = "TRADE_SHORT"
            direction = "SHORT"
        trace = result.get("decision_trace") if isinstance(result.get("decision_trace"), dict) else {}
        blackcat = trace.get("blackcat_signal") if isinstance(trace.get("blackcat_signal"), dict) else {}
        confluence = blackcat.get("confluence") if isinstance(blackcat.get("confluence"), dict) else trace
        reasons = [str(reason.get("code") or reason.get("message")) for reason in result.get("rejection_reasons") or [] if isinstance(reason, dict)]
        if result.get("setup_reason"):
            reasons.insert(0, str(result.get("setup_reason")))
        status = "ERROR" if result.get("status") == "ERROR" else "CANDIDATE" if action != "WAIT" else "WAIT"
        return {
            "strategy_id": result.get("strategy_name") or result.get("agent_id"),
            "agent_id": result.get("agent_id"),
            "symbol": result.get("symbol") or shared_context.get("symbol"),
            "timeframe": trace.get("timeframe") or shared_context.get("timeframe"),
            "raw_timeframe": shared_context.get("raw_timeframe"),
            "strategy_timeframe": shared_context.get("strategy_timeframe"),
            "resampled": shared_context.get("resampled"),
            "source_candle_count": shared_context.get("source_candle_count"),
            "raw_closed_candle_count": shared_context.get("raw_closed_candle_count"),
            "m15_bucket_count_total": shared_context.get("m15_bucket_count_total"),
            "m15_bucket_count_complete": shared_context.get("m15_bucket_count_complete"),
            "m15_bucket_count_incomplete": shared_context.get("m15_bucket_count_incomplete"),
            "strategy_candle_count": shared_context.get("strategy_candle_count"),
            "required_strategy_candle_count": shared_context.get("required_strategy_candle_count"),
            "dropped_latest_incomplete_bucket": shared_context.get("dropped_latest_incomplete_bucket"),
            "last_incomplete_bucket_start": shared_context.get("last_incomplete_bucket_start"),
            "candle_memory_status": shared_context.get("candle_memory_status"),
            "latest_raw_candle_timestamp": shared_context.get("latest_raw_candle_timestamp"),
            "latest_strategy_closed_candle_timestamp": shared_context.get("latest_strategy_closed_candle_timestamp"),
            "timestamp": blackcat.get("timestamp") or shared_context.get("latest_closed_candle_timestamp"),
            "action": action,
            "direction": direction,
            "confidence": float(result.get("confidence") or 0.0),
            "regime": blackcat.get("regime") or "UNKNOWN",
            "reasons": list(dict.fromkeys([reason for reason in reasons if reason] or ["no_actionable_signal"])),
            "candle_memory_used": blackcat.get("candle_memory_used") or len(shared_context.get("candles_25") or []),
            "available_candle_count": shared_context.get("available_candle_count"),
            "latest_closed_candle_timestamp": shared_context.get("latest_closed_candle_timestamp"),
            "structure_window_used": blackcat.get("structure_window_used") or len(shared_context.get("candles_100") or shared_context.get("candles_50") or []),
            "structure_high": shared_context.get("structure_high"),
            "structure_low": shared_context.get("structure_low"),
            "equilibrium": shared_context.get("equilibrium"),
            "range_position": shared_context.get("range_position"),
            "premium_discount_state": shared_context.get("premium_discount_state"),
            "bull_power": shared_context.get("bull_power"),
            "bear_power": shared_context.get("bear_power"),
            "structure_bias": shared_context.get("structure_bias"),
            "confluence": confluence,
            "status": status,
        }

    def select_candidate(self, outputs: list[dict[str, Any]], *, threshold: float = 0.60, conflict_margin: float = 0.05) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        candidates = [item for item in outputs if item.get("status") == "CANDIDATE" and float(item.get("confidence") or 0.0) >= threshold]
        low_confidence = [item for item in outputs if item.get("status") == "CANDIDATE" and float(item.get("confidence") or 0.0) < threshold]
        if not candidates:
            return None, {
                "reason": "confidence_rejection" if low_confidence else "no_candidate_found",
                "low_confidence_count": len(low_confidence),
                "conflict": False,
            }
        order = {entry.source_strategy: index for index, entry in enumerate(self.config.registered_agents)}
        candidates.sort(key=lambda item: (-float(item.get("confidence") or 0.0), order.get(str(item.get("strategy_id")), 999)))
        best = candidates[0]
        opposing = [item for item in candidates[1:] if item.get("direction") != best.get("direction")]
        if opposing and float(best.get("confidence") or 0.0) - float(opposing[0].get("confidence") or 0.0) < conflict_margin:
            return None, {
                "reason": "strategy_conflict",
                "conflict": True,
                "best": best,
                "opposing": opposing[0],
            }
        return best, {"reason": "selected_candidate", "conflict": False}

    def evaluate_agent(self, agent_id: str, shared_context: Optional[dict[str, Any]] = None) -> StrategyEvaluationResult:
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
        shared_context = shared_context or self.build_candle_context()
        guarded = self._context_guard_result(agent_id, shared_context)
        if guarded is not None:
            guarded.correlation_id = uuid4().hex
            guarded = self._augment_result_with_context(guarded, shared_context)
            guarded.event_id = self._publish_events(guarded)
            return guarded
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
                    candles=shared_context.get("closed_candles") or [],
                    context=self._input_context(shared_context),
                )
            )
        except Exception as exc:
            self._publish_diagnostic_event(
                AurixEventType.STRATEGY_PIPELINE_ERROR,
                {"diagnostic_event": "strategy_pipeline_error", "agent_id": agent_id, "strategy_name": agent.spec.name, "error": str(exc)},
                correlation_id=correlation_id,
            )
            result = StrategyEvaluationResult(
                agent_id=agent.spec.id,
                strategy_name=agent.spec.name,
                strategy_version=agent.spec.version,
                symbol=agent.spec.symbol,
                mode=agent.spec.mode,
                status="ERROR",
                setup_reason=f"exception in strategy loop: {exc}",
                rejection_reasons=[StrategyRejectionReason(code="strategy_pipeline_error", message=str(exc))],
                decision_trace={"error": str(exc), "agent_id": agent_id},
                correlation_id=correlation_id,
                safety=StrategyAgentSafety(),
            )
            result.event_id = self._publish_events(result)
            self._publish_diagnostic_event(
                AurixEventType.STRATEGY_EVALUATION_COMPLETED,
                {"diagnostic_event": "strategy_evaluation_completed", "agent_id": agent_id, "strategy_name": result.strategy_name, "result": "ERROR", "status": result.status},
                correlation_id=result.correlation_id,
            )
            return result
        result = self._augment_result_with_context(result, shared_context)
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
        cycle_id = uuid4().hex
        shared_context = self.build_candle_context()
        self._publish_diagnostic_event(
            AurixEventType.STRATEGY_REGISTRY_LOADED,
            {
                "diagnostic_event": "strategy_registry_loaded",
                "registered_count": len(self.registry.list_registered_agents()),
                "enabled_count": len(self.registry.get_enabled_agents()),
                "cycle_id": cycle_id,
            },
        )
        results = [self.evaluate_agent(agent.spec.id, shared_context) for agent in self.registry.get_enabled_agents()]
        outputs = [self.normalize_output(result.model_dump(), shared_context) for result in results]
        selected, selection = self.select_candidate(outputs)
        final_decision = "CANDIDATE_FOUND" if selected else "WAIT"
        memory_reason = shared_context.get("insufficient_reason") if shared_context.get("candle_memory_status") != "READY" else None
        block_reason = None if selected else memory_reason or selection.get("reason")
        trace = {
            "cycle_id": cycle_id,
            "timestamp": utc_now_iso(),
            "symbol": self.config.symbol,
            "timeframe": shared_context.get("timeframe"),
            "raw_timeframe": shared_context.get("raw_timeframe"),
            "strategy_timeframe": shared_context.get("strategy_timeframe"),
            "resampled": shared_context.get("resampled"),
            "source_candle_count": shared_context.get("source_candle_count"),
            "raw_closed_candle_count": shared_context.get("raw_closed_candle_count"),
            "source_closed_candle_count": shared_context.get("source_closed_candle_count"),
            "m15_bucket_count_total": shared_context.get("m15_bucket_count_total"),
            "m15_bucket_count_complete": shared_context.get("m15_bucket_count_complete"),
            "m15_bucket_count_incomplete": shared_context.get("m15_bucket_count_incomplete"),
            "strategy_candle_count": shared_context.get("strategy_candle_count"),
            "required_strategy_candle_count": shared_context.get("required_strategy_candle_count"),
            "incomplete_strategy_bucket_count": shared_context.get("incomplete_strategy_bucket_count"),
            "dropped_latest_incomplete_bucket": shared_context.get("dropped_latest_incomplete_bucket"),
            "last_incomplete_bucket_start": shared_context.get("last_incomplete_bucket_start"),
            "candle_memory_status": shared_context.get("candle_memory_status"),
            "spread_method": shared_context.get("spread_method"),
            "system_status": "CANDIDATE_FOUND" if selected else "SCANNING",
            "latest_closed_candle_timestamp": shared_context.get("latest_closed_candle_timestamp"),
            "latest_raw_candle_timestamp": shared_context.get("latest_raw_candle_timestamp"),
            "latest_strategy_closed_candle_timestamp": shared_context.get("latest_strategy_closed_candle_timestamp"),
            "available_candle_count": shared_context.get("available_candle_count"),
            "candle_memory_used": len(shared_context.get("candles_25") or []),
            "structure_context": {
                "structure_high": shared_context.get("structure_high"),
                "structure_low": shared_context.get("structure_low"),
                "structure_range": shared_context.get("structure_range"),
                "equilibrium": shared_context.get("equilibrium"),
                "range_position": shared_context.get("range_position"),
                "premium_discount_state": shared_context.get("premium_discount_state"),
                "bull_power": shared_context.get("bull_power"),
                "bear_power": shared_context.get("bear_power"),
                "structure_bias": shared_context.get("structure_bias"),
            },
            "strategies_evaluated": len(results),
            "strategy_outputs": outputs,
            "selected_candidate": selected,
            "selected_strategy_id": selected.get("strategy_id") if selected else None,
            "selected_action": selected.get("action") if selected else "WAIT",
            "selected_confidence": selected.get("confidence") if selected else 0.0,
            "selection_reason": memory_reason or selection.get("reason"),
            "final_decision": final_decision,
            "block_stage": "NONE" if selected else "DATA" if memory_reason else "STRATEGY",
            "block_reason": block_reason,
            "broker_execution_enabled": False,
            "paper_enabled": True,
            "recent_errors": [item for item in outputs if item.get("status") == "ERROR"],
        }
        self.store.save_trace(trace)
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
        latest_trace = self.store.latest_trace()
        active = self.registry.get_enabled_agents()
        latest_signal = next((item for item in reversed(latest) if item.get("status") == "SIGNAL"), None)
        latest_fast_rsi = next((item for item in reversed(latest) if item.get("agent_id") == "fast_rsi_first_reversal_v1"), None)
        latest_blackcat = next((item for item in reversed(latest) if item.get("agent_id") == "blackcat_cloud_v1" or item.get("strategy_name") == "blackcat_cloud_v1"), None)
        status.update(
            {
                "paper_trade_creation_allowed": safety.get("paper_trade_creation_allowed", False),
                "order_request_creation_allowed": safety.get("order_request_creation_allowed", False),
                "live_execution_allowed": safety.get("live_execution_allowed", False),
                "command_queueing_allowed": safety.get("command_queueing_allowed", False),
                "latest_signal": latest_signal,
                "latest_fast_rsi": latest_fast_rsi,
                "latest_blackcat_cloud_v1": latest_blackcat,
                "current_engine_status": "RUNNING" if self.config.enabled else "DISABLED",
                "last_heartbeat": latest_trace.get("timestamp") or status.get("last_evaluation_at"),
                "active_strategies": [agent.spec.id for agent in active],
                "active_strategy_count": len(active),
                "candle_memory_status": latest_trace.get("candle_memory_status")
                or (
                    "READY"
                    if int(latest_trace.get("strategy_candle_count") or latest_trace.get("available_candle_count") or 0)
                    >= int(latest_trace.get("required_strategy_candle_count") or 26)
                    else "WAITING_FOR_STRATEGY_TIMEFRAME_CANDLES"
                ),
                "latest_closed_candle_timestamp": latest_trace.get("latest_closed_candle_timestamp"),
                "latest_raw_candle_timestamp": latest_trace.get("latest_raw_candle_timestamp"),
                "latest_strategy_closed_candle_timestamp": latest_trace.get("latest_strategy_closed_candle_timestamp"),
                "available_closed_candle_count": latest_trace.get("available_candle_count"),
                "raw_timeframe": latest_trace.get("raw_timeframe"),
                "strategy_timeframe": latest_trace.get("strategy_timeframe"),
                "resampled": latest_trace.get("resampled"),
                "source_candle_count": latest_trace.get("source_candle_count"),
                "raw_closed_candle_count": latest_trace.get("raw_closed_candle_count"),
                "m15_bucket_count_total": latest_trace.get("m15_bucket_count_total"),
                "m15_bucket_count_complete": latest_trace.get("m15_bucket_count_complete"),
                "m15_bucket_count_incomplete": latest_trace.get("m15_bucket_count_incomplete"),
                "strategy_candle_count": latest_trace.get("strategy_candle_count"),
                "required_strategy_candle_count": latest_trace.get("required_strategy_candle_count"),
                "dropped_latest_incomplete_bucket": latest_trace.get("dropped_latest_incomplete_bucket"),
                "last_incomplete_bucket_start": latest_trace.get("last_incomplete_bucket_start"),
                "last_strategy_outputs": latest_trace.get("strategy_outputs") or [],
                "selected_candidate": latest_trace.get("selected_candidate"),
                "last_decision_trace": latest_trace,
                "last_block_reason": latest_trace.get("block_reason"),
                "recent_cycle_count": len(self.store.recent_traces()),
                "recent_errors": latest_trace.get("recent_errors") or [],
            }
        )
        return status

    def registry_payload(self) -> dict[str, Any]:
        return {"agents": [agent.model_dump() for agent in self.registry.list_registered_agents()]}

    def latest(self) -> list[dict[str, Any]]:
        return self.store.latest()

    def history(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        return self.store.history(limit)

    def recent_traces(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        return self.store.recent_traces(limit)

    def reset(self) -> dict[str, Any]:
        return self.store.reset(self.registry)
