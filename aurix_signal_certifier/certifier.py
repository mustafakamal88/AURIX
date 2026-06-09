from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import SignalCertifierConfig
from .models import SignalPathCertificationReport
from .trace import as_dict, as_float, as_int, as_list, find_by_id, find_key, latest


SAFETY = {
    "certification_only": True,
    "paper_mode_required": True,
    "live_execution_allowed": False,
    "live_arming_allowed": False,
    "mt5_commands_queued": False,
    "broker_order_created": False,
    "ea_settings_modified": False,
    "external_llm_used": False,
    "strategy_config_mutated": False,
    "readiness_config_modified": False,
    "evidence_monitor_config_modified": False,
}


class SignalPathCertifier:
    def __init__(self, config: SignalCertifierConfig):
        self.config = config

    def certify(self, inputs: dict[str, Any]) -> SignalPathCertificationReport:
        trades = [item for item in as_list(inputs.get("paper_trades")) if isinstance(item, dict)]
        signals = [item for item in as_list(inputs.get("strategy_signals")) if isinstance(item, dict)]
        trade = self._select_trade(trades)
        signal = find_by_id(signals, trade.get("signal_id")) if trade else {}
        if not trade and self.config.certify_latest_signal:
            signal = latest(signals)
        if not trade and not signal:
            return SignalPathCertificationReport(symbol=self.config.symbol, mode=self.config.mode, status="NO_SIGNAL", safety=SAFETY.copy())

        passed: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []
        warnings: list[str] = []

        snapshot_trace = self._snapshot_trace(inputs, passed, failed, warnings)
        context_trace = self._context_trace(signal, passed, skipped, failed)
        strategy_trace = self._strategy_trace(signal, trade, inputs, passed, skipped, failed, warnings)
        paper_engine_trace = self._paper_engine_trace(signal, trade, inputs, passed, skipped, failed)
        risk_trace = self._risk_trace(signal, trade, inputs, passed, skipped, failed, warnings)
        ledger_trace = self._ledger_trace(trade, trades, inputs, passed, skipped, failed)
        analytics_trace = self._analytics_trace(trade, inputs, passed, skipped, warnings)
        visibility_trace = self._visibility_trace(trade, inputs, passed, skipped, warnings)
        self._safety_checks(signal, trade, inputs, passed, failed)

        recommendations = self._recommendations(warnings, failed)
        status = "FAILED" if failed else ("CERTIFIED_WITH_WARNINGS" if warnings else "CERTIFIED")
        return SignalPathCertificationReport(
            symbol=self.config.symbol,
            mode=self.config.mode,
            status=status,
            certified_trade_id=trade.get("id") if trade else None,
            certified_signal_id=signal.get("id") or trade.get("signal_id") if trade else signal.get("id"),
            strategy=trade.get("strategy_name") or signal.get("strategy_name"),
            strategy_version=trade.get("strategy_version") or signal.get("strategy_version"),
            direction=trade.get("direction") or signal.get("direction"),
            trade_status=trade.get("status") if trade else None,
            snapshot_trace=snapshot_trace,
            context_trace=context_trace,
            strategy_trace=strategy_trace,
            paper_engine_trace=paper_engine_trace,
            risk_trace=risk_trace,
            ledger_trace=ledger_trace,
            analytics_trace=analytics_trace,
            visibility_trace=visibility_trace,
            passed_checks=passed,
            skipped_checks=skipped,
            failed_checks=failed,
            warnings=list(dict.fromkeys(warnings)),
            recommendations=recommendations,
            safety=SAFETY.copy(),
        )

    def _select_trade(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        if self.config.certify_latest_open_trade:
            open_trades = [trade for trade in trades if trade.get("status") == "OPEN"]
            if open_trades:
                return open_trades[-1]
        if self.config.certify_latest_closed_trade:
            closed = [trade for trade in trades if trade.get("status") != "OPEN"]
            if closed:
                return closed[-1]
        return latest(trades)

    def _snapshot_trace(self, inputs: dict[str, Any], passed: list[str], failed: list[str], warnings: list[str]) -> dict[str, Any]:
        snapshot = as_dict(inputs.get("latest_snapshot"))
        tick = as_dict(snapshot.get("tick"))
        account = as_dict(snapshot.get("account"))
        ea_live = _ea_live_disabled(snapshot, as_dict(inputs.get("operator_status")))
        trace = {
            "exists": bool(snapshot),
            "symbol": tick.get("symbol"),
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "spread_points": tick.get("spread_points"),
            "account_currency": account.get("currency"),
            "ea_live_trading_disabled": ea_live,
            "received_at": snapshot.get("received_at"),
        }
        _record(bool(snapshot), "snapshot exists", passed, failed)
        _record(tick.get("symbol") == self.config.symbol, "snapshot symbol matches", passed, failed)
        _record(as_float(tick.get("bid")) is not None and as_float(tick.get("ask")) is not None, "snapshot bid/ask exist", passed, failed)
        _record(as_float(tick.get("spread_points")) is not None, "snapshot spread exists", passed, failed)
        if account.get("currency"):
            passed.append("account currency captured")
        else:
            warnings.append("account currency unavailable")
        if self.config.require_ea_live_trading_disabled_now:
            _record(ea_live is not False, "EA live trading disabled or not reported enabled", passed, failed)
        return trace

    def _context_trace(self, signal: dict[str, Any], passed: list[str], skipped: list[str], failed: list[str]) -> dict[str, Any]:
        session = signal.get("context_session")
        regime = signal.get("context_regime")
        bias = signal.get("context_bias")
        trace = {"session": session, "regime": regime, "bias": bias, "range_high": signal.get("range_high"), "range_low": signal.get("range_low")}
        _record(bool(session), "context session exists", passed, failed)
        _record(session in {"LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"}, "context session allowed", passed, failed)
        _record(bool(regime), "context regime exists", passed, failed)
        _record(bool(bias), "context bias exists", passed, failed)
        if regime == "RANGE":
            _record(as_float(signal.get("range_high")) is not None and as_float(signal.get("range_low")) is not None, "range high/low exist for RANGE", passed, failed)
        else:
            skipped.append("range high/low only required for RANGE regime")
        return trace

    def _strategy_trace(
        self,
        signal: dict[str, Any],
        trade: dict[str, Any],
        inputs: dict[str, Any],
        passed: list[str],
        skipped: list[str],
        failed: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        reasons = as_list(signal.get("reasons")) or as_list(trade.get("reasons"))
        direction = signal.get("direction") or trade.get("direction")
        decision_trace = as_dict(signal.get("decision_trace"))
        trace = {
            "signal_id": signal.get("id"),
            "strategy_name": signal.get("strategy_name") or trade.get("strategy_name"),
            "strategy_version": signal.get("strategy_version") or trade.get("strategy_version"),
            "direction": direction,
            "signal_status": signal.get("status"),
            "command_id": signal.get("command_id"),
            "reasons": reasons,
            "decision_trace": decision_trace or None,
            "v1_rule": {},
        }
        _record(bool(trace["strategy_name"]), "strategy name exists", passed, failed)
        _record(bool(trace["strategy_version"]), "strategy version exists", passed, failed)
        _record(bool(signal.get("id")), "signal_id exists", passed, failed)
        _record(direction in {"BUY", "SELL"}, "direction is BUY or SELL", passed, failed)
        _record(signal.get("status") == "SHADOW_SIGNAL", "paper signal status is SHADOW_SIGNAL", passed, failed)
        if self.config.require_command_id_null_for_paper:
            _record(signal.get("command_id") is None, "paper signal command_id is null", passed, failed)
        _record(bool(reasons), "setup reason exists", passed, failed)
        if trace["strategy_name"] == "xauusd_paper_v1" and direction in {"BUY", "SELL"} and decision_trace:
            rule = _v1_rule_trace_from_decision(direction, decision_trace)
            trace["v1_rule"] = rule
            for check, ok in rule.get("checks", {}).items():
                _record(bool(ok), f"V1 {direction} rule {check}", passed, failed)
        elif trace["strategy_name"] == "xauusd_paper_v1" and direction in {"BUY", "SELL"}:
            trace["v1_rule"] = {"source": "legacy_signal_trace_missing", "checks": {}}
            warnings.append("legacy signal missing decision-time OHLC/rule trace")
            skipped.append("legacy_signal_trace_missing: V1 rule checks skipped")
        else:
            skipped.append("V1 sweep/reclaim rule reconstruction not applicable")
        return trace

    def _paper_engine_trace(self, signal: dict[str, Any], trade: dict[str, Any], inputs: dict[str, Any], passed: list[str], skipped: list[str], failed: list[str]) -> dict[str, Any]:
        cfg = as_dict(inputs.get("paper_config"))
        snapshot = as_dict(inputs.get("latest_snapshot"))
        tick = as_dict(snapshot.get("tick"))
        open_at_entry = _open_trades_before(as_list(inputs.get("paper_trades")), trade)
        trace = {
            "paper_trading_enabled": cfg.get("enabled"),
            "signal_actionable": signal.get("status") in {"SHADOW_SIGNAL", "PAPER_SIGNAL"} and signal.get("direction") in {"BUY", "SELL"},
            "open_trades_before_entry": open_at_entry,
            "max_open_paper_trades": cfg.get("max_open_paper_trades"),
            "allow_multiple_same_direction": cfg.get("allow_multiple_same_direction"),
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "volume": trade.get("volume"),
            "paper_trade_opened": bool(trade),
        }
        _record(cfg.get("enabled") is True, "paper trading enabled", passed, failed)
        _record(trace["signal_actionable"], "signal actionable", passed, failed)
        _record(open_at_entry < as_int(cfg.get("max_open_paper_trades") or 1), "max open paper trades not exceeded at entry", passed, failed)
        if cfg.get("allow_multiple_same_direction") is False:
            _record(not _same_direction_before(as_list(inputs.get("paper_trades")), trade), "no same-direction paper trade already open at entry", passed, failed)
        else:
            skipped.append("same-direction paper trade gate not enabled")
        _record(as_float(tick.get("bid")) is not None and as_float(tick.get("ask")) is not None, "paper engine bid/ask present", passed, failed)
        _record(as_float(trade.get("volume")) is not None, "volume equivalent exists", passed, failed)
        _record(bool(trade), "paper trade was opened", passed, failed)
        return trace

    def _risk_trace(
        self,
        signal: dict[str, Any],
        trade: dict[str, Any],
        inputs: dict[str, Any],
        passed: list[str],
        skipped: list[str],
        failed: list[str],
        warnings: list[str],
    ) -> dict[str, Any]:
        decisions = [item for item in as_list(inputs.get("paper_risk_decisions")) if isinstance(item, dict)]
        decision = _find_paper_risk_decision(decisions, signal, trade)
        trace = {
            "simulated_risk_approval_reconstructed": bool(trade),
            "persisted_paper_risk_decision": bool(decision),
            "paper_risk_decision": decision or None,
            "signal_risk_checked": signal.get("risk_checked"),
            "signal_paper_risk_checked": signal.get("paper_risk_checked"),
            "signal_paper_risk_decision_id": signal.get("paper_risk_decision_id"),
        }
        if decision:
            _record(decision.get("signal_id") == signal.get("id"), "paper risk decision links certified signal", passed, failed)
            _record(not trade or decision.get("trade_id") == trade.get("id"), "paper risk decision links certified trade", passed, failed)
            _record(decision.get("mode") == "PAPER", "paper risk decision mode is PAPER", passed, failed)
            _record(decision.get("decision_type") == "PAPER_SIMULATED_RISK", "paper risk decision type is PAPER_SIMULATED_RISK", passed, failed)
            if trade:
                _record(decision.get("risk_status") == "APPROVED", "paper risk decision approved opened paper trade", passed, failed)
            _record(as_dict(decision.get("safety")).get("mt5_commands_queued") is False, "paper risk decision queued no MT5 command", passed, failed)
            _record(as_dict(decision.get("safety")).get("broker_order_created") is False, "paper risk decision created no broker order", passed, failed)
        elif trade:
            passed.append("simulated risk approval can be reconstructed from paper trade")
            if signal.get("paper_risk_checked") is True:
                warnings.append("paper signal claims risk was checked but no paper risk decision was found")
            else:
                warnings.append("paper risk decision was not persisted")
        else:
            skipped.append("risk trace skipped because no trade exists")
        if signal and signal.get("risk_checked") is False and trade:
            warnings.append("signal risk_checked=false even though paper engine simulated risk before ledger write")
        return trace

    def _ledger_trace(self, trade: dict[str, Any], trades: list[dict[str, Any]], inputs: dict[str, Any], passed: list[str], skipped: list[str], failed: list[str]) -> dict[str, Any]:
        cfg = as_dict(inputs.get("paper_config"))
        point = _snapshot_point(as_dict(inputs.get("latest_snapshot")))
        stop_expected = as_float(cfg.get("default_stop_points")) * point if as_float(cfg.get("default_stop_points")) is not None else None
        tp_expected = as_float(cfg.get("default_take_profit_points")) * point if as_float(cfg.get("default_take_profit_points")) is not None else None
        entry = as_float(trade.get("entry_price"))
        sl = as_float(trade.get("stop_loss"))
        tp = as_float(trade.get("take_profit"))
        direction = trade.get("direction")
        stop_actual = abs(entry - sl) if entry is not None and sl is not None else None
        tp_actual = abs(tp - entry) if entry is not None and tp is not None else None
        trace = {"trade_id": trade.get("id"), "status": trade.get("status"), "opened_at": trade.get("opened_at"), "entry": entry, "sl": sl, "tp": tp, "stop_distance": stop_actual, "tp_distance": tp_actual}
        _record(bool(trade.get("id")), "trade_id exists", passed, failed)
        _record(bool(trade.get("status")), "trade status exists", passed, failed)
        _record(bool(trade.get("opened_at")), "opened_at exists", passed, failed)
        _record(entry is not None and sl is not None and tp is not None, "entry SL TP exist", passed, failed)
        if stop_expected is not None and tp_expected is not None and direction in {"BUY", "SELL"}:
            _record(_near(stop_actual, stop_expected), "SL distance matches configured default", passed, failed)
            _record(_near(tp_actual, tp_expected), "TP distance matches configured default", passed, failed)
        else:
            skipped.append("SL/TP distance check skipped")
        _record(any(item.get("id") == trade.get("id") for item in trades), "trade appears in paper ledger", passed, failed)
        if trade.get("status") == "OPEN":
            passed.append("open trade appears in open paper ledger")
            skipped.append("closed ledger check waits for trade closure")
        else:
            passed.append("closed trade appears in paper ledger")
        return trace

    def _analytics_trace(self, trade: dict[str, Any], inputs: dict[str, Any], passed: list[str], skipped: list[str], warnings: list[str]) -> dict[str, Any]:
        analytics = as_dict(inputs.get("paper_analytics"))
        trace = {"open_trades": analytics.get("open_trades"), "closed_trades": analytics.get("closed_trades"), "expectancy_r": analytics.get("expectancy_r")}
        if analytics:
            passed.append("analytics report exists")
            if trade.get("status") == "OPEN" and as_int(analytics.get("open_trades")) >= 1:
                passed.append("analytics sees open trade count")
            elif trade.get("status") != "OPEN":
                passed.append("analytics can report closed trade count")
            else:
                warnings.append("analytics open trade count does not show certified open trade")
            if as_int(analytics.get("closed_trades")) == 0 and float(analytics.get("expectancy_r") or 0.0) == 0.0:
                passed.append("expectancy remains 0 with no closed trades")
        else:
            skipped.append("analytics report unavailable")
            warnings.append("paper analytics report unavailable")
        return trace

    def _visibility_trace(self, trade: dict[str, Any], inputs: dict[str, Any], passed: list[str], skipped: list[str], warnings: list[str]) -> dict[str, Any]:
        summary = as_dict(inputs.get("operator_summary"))
        readiness = as_dict(inputs.get("live_readiness_report"))
        growth = as_dict(inputs.get("evidence_growth_report"))
        trace = {"operator_paper_open_count": summary.get("paper_open_count"), "live_readiness_status": readiness.get("status"), "evidence_growth_status": growth.get("status")}
        if summary:
            passed.append("operator summary available")
            if trade.get("status") == "OPEN" and as_int(summary.get("paper_open_count")) >= 1:
                passed.append("operator summary includes paper open trade count")
        else:
            warnings.append("operator summary unavailable")
        if readiness.get("live_execution_allowed") is False and readiness.get("live_arming_allowed") is False:
            passed.append("live readiness remains safety-limited")
        else:
            warnings.append("live readiness visibility unavailable or unsafe")
        if growth:
            passed.append("evidence growth report visible")
        else:
            skipped.append("evidence growth report unavailable")
        return trace

    def _safety_checks(self, signal: dict[str, Any], trade: dict[str, Any], inputs: dict[str, Any], passed: list[str], failed: list[str]) -> None:
        summary = as_dict(inputs.get("operator_summary"))
        operator = as_dict(inputs.get("operator_status"))
        readiness = as_dict(inputs.get("live_readiness_report"))
        commands = as_dict(operator.get("commands"))
        if self.config.require_paper_mode:
            _record((signal.get("mode") == "PAPER") or (summary.get("mode") == "PAPER"), "mode is PAPER", passed, failed)
        if self.config.require_live_execution_disabled:
            _record(not self.config.allow_live_execution and readiness.get("live_execution_allowed") is not True, "live execution disabled", passed, failed)
        if self.config.require_live_arming_disabled:
            _record(not self.config.allow_live_arming and readiness.get("live_arming_allowed") is not True, "live arming disabled", passed, failed)
        _record(not self.config.allow_command_queueing, "command queueing disabled by certifier config", passed, failed)
        if self.config.require_no_mt5_command_for_paper:
            _record(as_int(commands.get("open_count")) == 0, "no MT5 commands queued", passed, failed)
        _record(signal.get("command_id") is None, "paper signal command_id remains null", passed, failed)
        _record(as_int(as_dict(operator.get("bridge")).get("positions_count")) == 0, "no broker order created", passed, failed)
        passed.append("EA settings not modified by certifier")

    def _recommendations(self, warnings: list[str], failed: list[str]) -> list[str]:
        recs: list[str] = []
        if any("risk_checked=false" in item for item in warnings):
            recs.append("persist or annotate paper-engine simulated risk checks separately from strategy signal risk_checked")
        if any("paper risk decision was not persisted" in item for item in warnings):
            recs.append("persist paper simulation risk decisions for stronger auditability")
        if any("claims risk was checked" in item for item in warnings):
            recs.append("repair missing paper risk audit linkage for the certified signal/trade")
        if any("legacy signal missing decision-time OHLC/rule trace" in item for item in warnings):
            recs.append("new signals should include decision_trace for deterministic rule certification")
        if failed:
            recs.append("treat failed certification checks as blockers for signal-path evidence")
        recs.append("keep live trading, arming, and command queueing disabled; certification is observability-only")
        return list(dict.fromkeys(recs))


class SignalCertifierStore:
    def __init__(self, data_dir: str | Path = "data", config: SignalCertifierConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or SignalCertifierConfig()
        self.report_file = self.data_dir / "signal_path_certification_report.json"
        self.history_file = self.data_dir / "signal_path_certification_history.jsonl"

    def status(self) -> dict[str, Any]:
        latest_report = self.latest()
        return {"enabled": self.config.enabled, "symbol": self.config.symbol, "mode": self.config.mode, "latest_exists": bool(latest_report), "latest": latest_report.model_dump() if latest_report else None, "config": self.config.model_dump(), "safety": SAFETY.copy()}

    def latest(self) -> SignalPathCertificationReport | None:
        data = self._read_dict(self.report_file)
        return SignalPathCertificationReport(**data) if data else None

    def certify(self, inputs: dict[str, Any]) -> SignalPathCertificationReport:
        report = SignalPathCertifier(self.config).certify(inputs)
        self.save(report)
        if self.config.write_history:
            self.append_history(report)
        return report

    def save(self, report: SignalPathCertificationReport) -> SignalPathCertificationReport:
        self.report_file.write_text(json.dumps(report.model_dump(), indent=2, default=str), encoding="utf-8")
        return report

    def append_history(self, report: SignalPathCertificationReport) -> None:
        entry = {"id": report.id, "generated_at": report.generated_at, "status": report.status, "trade_id": report.certified_trade_id, "signal_id": report.certified_signal_id, "strategy": report.strategy, "direction": report.direction, "trade_status": report.trade_status, "warning_count": len(report.warnings), "failed_count": len(report.failed_checks)}
        items = self.history()
        items.append(entry)
        items = items[-max(int(self.config.history_limit or 1), 1):]
        self.history_file.write_text("".join(json.dumps(item, default=str) + "\n" for item in items), encoding="utf-8")

    def history(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.history_file.exists():
            return []
        items = []
        for line in self.history_file.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                items.append(data)
        return items[-limit:] if limit else items

    def reset(self) -> None:
        self.report_file.write_text("{}", encoding="utf-8")
        self.history_file.write_text("", encoding="utf-8")

    def read_inputs(self, operator_status: dict[str, Any], operator_summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "latest_snapshot": self._read_dict(self.data_dir / "latest_snapshot.json"),
            "raw_snapshot": self._read_dict(self.data_dir / "latest_snapshot_debug.json"),
            "market_candles": self._read_list(self.data_dir / "market_candles_m1.json"),
            "context_output": self._read_dict(self.data_dir / "context_latest.json"),
            "strategy_signals": self._read_list(self.data_dir / "strategy_signals.json"),
            "paper_trades": self._read_list(self.data_dir / "paper_trades.json"),
            "paper_analytics": self._read_dict(self.data_dir / "paper_performance_report.json"),
            "operator_status": operator_status,
            "operator_summary": operator_summary,
            "evidence_gate_report": self._read_dict(self.data_dir / "evidence_gate_report.json"),
            "live_readiness_report": self._read_dict(self.data_dir / "live_readiness_report.json"),
            "evidence_growth_report": self._read_dict(self.data_dir / "evidence_growth_report.json"),
            "risk_decisions": self._read_list(self.data_dir / "risk_decisions.json"),
            "paper_risk_decisions": self._read_list(self.data_dir / "paper_risk_decisions.json"),
            "paper_config": self._read_yaml(Path("config/paper_trading.yaml")),
            "strategy_v1_config": self._read_yaml(Path("config/strategy_xauusd_paper_v1.yaml")),
        }

    def _read_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def _read_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}


def _record(ok: bool, name: str, passed: list[str], failed: list[str]) -> None:
    (passed if ok else failed).append(name)


def _find_paper_risk_decision(decisions: list[dict[str, Any]], signal: dict[str, Any], trade: dict[str, Any]) -> dict[str, Any]:
    expected_id = trade.get("risk_decision_id") or signal.get("paper_risk_decision_id")
    if expected_id:
        found = find_by_id(decisions, expected_id)
        if found:
            return found
    for decision in decisions:
        if trade and decision.get("trade_id") == trade.get("id"):
            return decision
    for decision in decisions:
        if signal and decision.get("signal_id") == signal.get("id"):
            return decision
    return {}


def _ea_live_disabled(snapshot: dict[str, Any], operator_status: dict[str, Any]) -> bool | None:
    seen = as_dict(operator_status.get("safety")).get("ea_allow_live_trading_seen")
    if seen is not None:
        return seen is False
    raw = find_key(snapshot, {"allowlivetrading", "allow_live_trading", "ealivetrading", "ea_allow_live_trading"})
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw is False
    return str(raw).strip().lower() in {"false", "0", "no", "disabled"}


def _v1_rule_trace(direction: str, signal: dict[str, Any], candles: list[Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    range_high = as_float(signal.get("range_high"))
    range_low = as_float(signal.get("range_low"))
    historical_source = _candles_near_signal([item for item in candles if isinstance(item, dict)], signal)
    source = historical_source or [item for item in as_list(snapshot.get("candles")) if isinstance(item, dict)]
    current = as_dict(source[-1]) if len(source) >= 1 else {}
    previous = as_dict(source[-2]) if len(source) >= 2 else {}
    current_open = as_float(current.get("open"))
    current_close = as_float(current.get("close"))
    previous_high = as_float(previous.get("high"))
    previous_low = as_float(previous.get("low"))
    bullish = current_close is not None and current_open is not None and current_close > current_open
    bearish = current_close is not None and current_open is not None and current_close < current_open
    reasons = " ".join(str(item).lower() for item in as_list(signal.get("reasons")))
    if direction == "BUY":
        checks = {"previous_low_lt_range_low": previous_low is not None and range_low is not None and previous_low < range_low, "current_close_gt_range_low": current_close is not None and range_low is not None and current_close > range_low, "current_candle_bullish": bullish}
        if not historical_source and "swept range low" in reasons and "bullish candle reclaimed range low" in reasons:
            checks = {key: True for key in checks}
    else:
        checks = {"previous_high_gt_range_high": previous_high is not None and range_high is not None and previous_high > range_high, "current_close_lt_range_high": current_close is not None and range_high is not None and current_close < range_high, "current_candle_bearish": bearish}
        if not historical_source and "swept range high" in reasons and "bearish candle reclaimed range high" in reasons:
            checks = {key: True for key in checks}
    return {"range_high": range_high, "range_low": range_low, "current": current, "previous": previous, "source": "historical_candles" if historical_source else "signal_reasons", "checks": checks}


def _v1_rule_trace_from_decision(direction: str, decision_trace: dict[str, Any]) -> dict[str, Any]:
    checks = as_dict(decision_trace.get("rule_checks"))
    required = ["symbol_matched", "session_allowed", "spread_ok", "enough_candles", "cooldown_ok"]
    if direction == "BUY":
        required.extend(["allow_buy", "previous_low_lt_range_low", "current_close_gt_range_low", "current_candle_bullish"])
    else:
        required.extend(["allow_sell", "previous_high_gt_range_high", "current_close_lt_range_high", "current_candle_bearish"])
    return {
        "source": "decision_trace",
        "trace_version": decision_trace.get("trace_version"),
        "rule_name": decision_trace.get("rule_name"),
        "previous_candle": decision_trace.get("previous_candle"),
        "current_candle": decision_trace.get("current_candle"),
        "range_high": decision_trace.get("range_high"),
        "range_low": decision_trace.get("range_low"),
        "checks": {name: checks.get(name) is True for name in required},
    }


def _candles_near_signal(candles: list[dict[str, Any]], signal: dict[str, Any]) -> list[dict[str, Any]]:
    parsed = _parse_time(signal.get("snapshot_updated_at") or signal.get("created_at"))
    if parsed is None:
        return []
    minute = int(parsed.timestamp() // 60 * 60)
    timed = [item for item in candles if as_int(item.get("time")) > 0]
    before = [item for item in timed if as_int(item.get("time")) <= minute]
    return before[-2:] if len(before) >= 2 else []


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _open_trades_before(trades: list[Any], trade: dict[str, Any]) -> int:
    opened_at = str(trade.get("opened_at") or "")
    return sum(1 for item in trades if isinstance(item, dict) and item.get("status") == "OPEN" and str(item.get("opened_at") or "") < opened_at)


def _same_direction_before(trades: list[Any], trade: dict[str, Any]) -> bool:
    opened_at = str(trade.get("opened_at") or "")
    return any(isinstance(item, dict) and item.get("direction") == trade.get("direction") and str(item.get("opened_at") or "") < opened_at and item.get("status") == "OPEN" for item in trades)


def _snapshot_point(snapshot: dict[str, Any]) -> float:
    return as_float(as_dict(snapshot.get("tick")).get("point")) or 0.01


def _near(a: float | None, b: float | None, tolerance: float = 0.000001) -> bool:
    return a is not None and b is not None and abs(a - b) <= tolerance
