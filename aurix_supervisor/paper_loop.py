from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from aurix_bridge_server.models import utc_now_iso
from aurix_context_engine import ContextEngine
from aurix_market_data import MarketDataRecorder
from aurix_market_data.config import MarketDataConfig
from aurix_market_data.quality import build_quality_report
from aurix_paper_trading import PaperLedger, PaperTradingEngine
from aurix_strategy_engine.models import StrategySignal
from aurix_strategy_engine.xauusd_paper_v1 import XauusdPaperV1Config, evaluate_xauusd_paper_v1

from .config import SupervisorConfig
from .models import SupervisorStatus


class PaperSupervisor:
    def __init__(
        self,
        data_dir: str | Path,
        config: SupervisorConfig,
        store: Any,
        market_recorder: MarketDataRecorder,
        context_engine: ContextEngine,
        xauusd_paper_v1_config: XauusdPaperV1Config,
        paper_engine: PaperTradingEngine,
        paper_ledger: PaperLedger,
        market_config: MarketDataConfig,
        paper_risk_audit_store: Any | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.data_dir / "supervisor_status.json"
        self.config = config
        self.store = store
        self.market_recorder = market_recorder
        self.context_engine = context_engine
        self.xauusd_paper_v1_config = xauusd_paper_v1_config
        self.paper_engine = paper_engine
        self.paper_ledger = paper_ledger
        self.market_config = market_config
        self.paper_risk_audit_store = paper_risk_audit_store

    def status(self) -> SupervisorStatus:
        data = self._read_json(self.status_file, None)
        if isinstance(data, dict):
            return SupervisorStatus(**data)
        return self._base_status(loop_count=0)

    def reset(self) -> SupervisorStatus:
        status = self._base_status(loop_count=0)
        self._save_status(status)
        return status

    def run_once(self) -> SupervisorStatus:
        previous = self.status()
        status = self._base_status(loop_count=previous.loop_count + 1)
        status.running = True
        snapshot = self.store.latest_snapshot()
        context_data: Optional[dict[str, Any]] = None
        signal: Optional[StrategySignal] = None

        try:
            status.last_snapshot_updated_at = snapshot.get("received_at") if snapshot else None
            market_quality = self._market_quality(snapshot)
            status.market_quality_ok = bool(market_quality.get("ok"))

            if not snapshot:
                status.errors.append("snapshot missing")

            if not self.config.enabled:
                status.errors.append("supervisor disabled")
            elif self.config.mode != "PAPER":
                status.errors.append("supervisor mode must be PAPER")
            elif self.config.allow_command_queueing:
                status.errors.append("allow_command_queueing must remain false")

            if self.config.run_context:
                context = self.context_engine.evaluate(
                    snapshot=snapshot,
                    recorded_candles=self.market_recorder.list_candles(),
                    market_quality=market_quality,
                )
                self.context_engine.store(context)
                context_data = context.model_dump()
                status.context_id = context.id

            blocked_by_quality = self.config.require_market_quality_ok and not status.market_quality_ok
            if blocked_by_quality:
                status.errors.extend(str(reason) for reason in market_quality.get("reasons") or ["market quality not ok"])

            if self.config.enabled and not blocked_by_quality and self.config.run_strategy:
                signal = evaluate_xauusd_paper_v1(
                    snapshot=snapshot,
                    context=context_data,
                    candles=self.market_recorder.list_candles(),
                    previous_signals=self.store.list_strategy_signals(),
                    config=self.xauusd_paper_v1_config,
                )
                self.store.add_strategy_signal(signal.model_dump())
                status.strategy_signal_id = signal.id

                if self.config.run_paper_trading:
                    trade, result = self.paper_engine.create_from_signal(
                        signal=signal,
                        snapshot=snapshot,
                        open_trades=self.paper_ledger.list_open_trades(),
                        previous_risk_decisions=self.store.list_risk_decisions(),
                    )
                    status.paper_created = bool(result.get("created"))
                    self._persist_paper_risk(signal, trade, result)
                    if trade is not None:
                        self.paper_ledger.add_trade(trade)

            if self.config.run_paper_trading:
                trades, updated = self.paper_engine.update_open_trades(snapshot, self.paper_ledger.list_trades())
                self.paper_ledger.save_trades(trades)
                status.paper_closed_now_count = len(updated)

            status.paper_open_count = len(self.paper_ledger.list_open_trades())
        except Exception as exc:
            status.errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            status.running = False
            status.last_heartbeat_at = utc_now_iso()
            status.safety = self._safety(signal)
            self._save_status(status)

        return status

    def _base_status(self, loop_count: int) -> SupervisorStatus:
        return SupervisorStatus(
            enabled=self.config.enabled,
            mode=self.config.mode,
            running=False,
            market_quality_ok=False,
            loop_count=loop_count,
            safety=self._safety(None),
        )

    def _market_quality(self, snapshot: Optional[dict[str, Any]]) -> dict[str, Any]:
        quality_config = self.market_config.model_copy(update={"max_snapshot_age_seconds": self.config.max_snapshot_age_seconds})
        return build_quality_report(snapshot, quality_config)

    def _safety(self, signal: Optional[StrategySignal]) -> dict[str, Any]:
        return {
            "paper_only": True,
            "mode": self.config.mode,
            "allow_command_queueing": self.config.allow_command_queueing,
            "mt5_commands_queued": False,
            "open_market_endpoint_called": False,
            "signal_command_id": signal.command_id if signal else None,
        }

    def _persist_paper_risk(self, signal: StrategySignal, trade: Any, result: dict[str, Any]) -> None:
        decision = result.get("paper_risk_decision")
        if not isinstance(decision, dict):
            return
        if self.paper_risk_audit_store is not None:
            self.paper_risk_audit_store.add_decision(decision)
        updates = {
            "paper_risk_checked": True,
            "paper_risk_decision_id": decision.get("id"),
            "paper_risk_status": decision.get("risk_status"),
            "paper_risk_checked_at": decision.get("created_at"),
            "risk_check_source": "PAPER_ENGINE_SIMULATION",
        }
        self.store.update_strategy_signal(signal.id, updates)
        for key, value in updates.items():
            setattr(signal, key, value)
        if trade is not None:
            trade.risk_decision_id = decision.get("id")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _save_status(self, status: SupervisorStatus) -> None:
        self.status_file.write_text(json.dumps(status.model_dump(), indent=2, default=str), encoding="utf-8")
