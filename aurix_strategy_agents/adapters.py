from __future__ import annotations

from typing import Any, Optional

from .base import StrategyAgent
from .models import (
    StrategyEvaluationInput,
    StrategyEvaluationResult,
    StrategyRejectionReason,
)


SIGNAL_STATUSES = {"PAPER_SIGNAL", "SHADOW_SIGNAL", "SIGNAL"}


def _setup_reason(signal: Optional[dict[str, Any]]) -> Optional[str]:
    if not signal:
        return None
    reasons = signal.get("reasons")
    if isinstance(reasons, list) and reasons:
        return "; ".join(str(reason) for reason in reasons)
    return signal.get("setup_reason")


def _reject(code: str, message: str) -> StrategyRejectionReason:
    return StrategyRejectionReason(code=code, message=message)


class ExistingSignalAdapter(StrategyAgent):
    source_strategy: str = ""

    def _latest_matching_signal(self, evaluation_input: StrategyEvaluationInput) -> Optional[dict[str, Any]]:
        signal = evaluation_input.latest_signal
        if not signal:
            return None
        if signal.get("strategy_name") != self.source_strategy:
            return None
        return signal

    def evaluate(self, evaluation_input: StrategyEvaluationInput) -> StrategyEvaluationResult:
        signal = self._latest_matching_signal(evaluation_input)
        if not signal:
            return StrategyEvaluationResult(
                agent_id=self.spec.id,
                strategy_name=self.source_strategy,
                strategy_version=self.spec.version,
                symbol=evaluation_input.symbol,
                mode=self.spec.mode,
                status="NO_SIGNAL",
                rejection_reasons=[_reject("NO_EXISTING_SIGNAL", "No existing local strategy signal was available for this adapter.")],
            )

        raw_status = str(signal.get("status") or "NO_SIGNAL")
        direction = signal.get("direction")
        has_signal = raw_status in SIGNAL_STATUSES and direction in {"BUY", "SELL"}
        status = "SIGNAL" if has_signal else "NO_SIGNAL"
        warnings: list[str] = []
        if signal.get("command_id") is not None:
            warnings.append("source signal command_id was not null; adapter output forced it to null")
        return StrategyEvaluationResult(
            agent_id=self.spec.id,
            strategy_name=str(signal.get("strategy_name") or self.source_strategy),
            strategy_version=str(signal.get("strategy_version") or self.spec.version),
            symbol=str(signal.get("symbol") or evaluation_input.symbol),
            mode=self.spec.mode,
            status=status,
            direction=direction if has_signal else None,
            confidence=float(signal.get("confidence") or 0.0),
            entry_reference=signal.get("entry_reference"),
            stop_loss_reference=signal.get("stop_loss_reference"),
            take_profit_reference=signal.get("take_profit_reference"),
            setup_reason=_setup_reason(signal),
            decision_trace=signal.get("decision_trace") if isinstance(signal.get("decision_trace"), dict) else None,
            rejection_reasons=[] if has_signal else [_reject(raw_status, _setup_reason(signal) or raw_status)],
            warnings=warnings,
        )


class XauusdPaperV1Adapter(ExistingSignalAdapter):
    source_strategy = "xauusd_paper_v1"


class XauusdPaperV2Adapter(ExistingSignalAdapter):
    source_strategy = "xauusd_paper_v2"

    def evaluate(self, evaluation_input: StrategyEvaluationInput) -> StrategyEvaluationResult:
        signal = self._latest_matching_signal(evaluation_input)
        if not signal:
            return StrategyEvaluationResult(
                agent_id=self.spec.id,
                strategy_name=self.source_strategy,
                strategy_version=self.spec.version,
                symbol=evaluation_input.symbol,
                mode=self.spec.mode,
                status="NO_SIGNAL",
                rejection_reasons=[_reject("NO_EXISTING_SIGNAL", "No existing local V2 strategy signal was available.")],
            )
        raw_status = str(signal.get("status") or "NO_SIGNAL")
        if raw_status.startswith("SKIPPED_"):
            return StrategyEvaluationResult(
                agent_id=self.spec.id,
                strategy_name=str(signal.get("strategy_name") or self.source_strategy),
                strategy_version=str(signal.get("strategy_version") or self.spec.version),
                symbol=str(signal.get("symbol") or evaluation_input.symbol),
                mode=self.spec.mode,
                status="SKIPPED",
                direction=None,
                confidence=float(signal.get("confidence") or 0.0),
                setup_reason=_setup_reason(signal),
                decision_trace=signal.get("decision_trace") if isinstance(signal.get("decision_trace"), dict) else None,
                rejection_reasons=[_reject(raw_status, _setup_reason(signal) or raw_status)],
            )
        return super().evaluate(evaluation_input)
