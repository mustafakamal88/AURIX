from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .arming_plan import build_manual_checklist, build_micro_live_plan
from .config import LiveReadinessConfig
from .models import LiveReadinessReport


SAFETY = {
    "readiness_only": True,
    "live_execution_allowed": False,
    "live_arming_allowed": False,
    "mt5_commands_queued": False,
    "ea_settings_modified": False,
    "external_llm_used": False,
    "strategy_config_mutated": False,
}


class LiveReadinessEvaluator:
    def __init__(self, config: LiveReadinessConfig):
        self.config = config

    def evaluate(self, inputs: dict[str, Any]) -> LiveReadinessReport:
        evidence = _as_dict(inputs.get("evidence_gate_report"))
        forward = _as_dict(inputs.get("forward_test_status"))
        long_forward = _as_dict(inputs.get("long_forward_test_status"))
        operator_status = _as_dict(inputs.get("operator_status"))
        operator_summary = _as_dict(inputs.get("operator_summary"))
        market_quality = _as_dict(inputs.get("market_quality"))
        paper_analytics = _as_dict(inputs.get("paper_analytics"))
        backtest = _as_dict(inputs.get("backtest_report"))
        research = _as_dict(inputs.get("research_sweep"))
        journal = _as_dict(inputs.get("journal_status"))
        ai_review = _as_dict(inputs.get("ai_review_report"))
        commands = _as_dict(operator_status.get("commands"))
        paper = _as_dict(operator_status.get("paper"))
        snapshot = _as_dict(inputs.get("latest_snapshot"))

        campaign = _as_dict(forward.get("campaign"))
        evidence_status = str(evidence.get("status") or "")
        closed_paper_trades = _first_int(
            paper_analytics.get("closed_trades"),
            campaign.get("closed_paper_trades"),
            paper.get("closed_trades"),
            operator_summary.get("paper_closed_trades"),
        )
        recorded_candles = _first_int(
            campaign.get("recorded_candles"),
            long_forward.get("recorded_candles"),
            inputs.get("recorded_candles"),
        )
        forward_days = _first_int(
            campaign.get("days_observed"),
            long_forward.get("days_observed"),
            inputs.get("forward_days"),
        )
        open_commands = _first_int(commands.get("open_count"), inputs.get("open_command_count"))
        open_paper_trades = _first_int(paper.get("open_trades"), operator_summary.get("paper_open_count"))
        operator_ok = bool(operator_summary.get("ok"))
        market_quality_ok = bool(operator_summary.get("market_quality_ok") or market_quality.get("ok"))
        ea_live_disabled = _ea_live_trading_disabled(operator_status, snapshot)

        checks = {
            "evidence_gate_eligible": _check(
                not self.config.require_evidence_gate_eligible or (bool(evidence) and evidence_status != "BLOCKED"),
                evidence_status or None,
                "not BLOCKED",
                "evidence gate is blocked or unavailable",
            ),
            "forward_test_completed": _check(
                not self.config.require_forward_test_completed or campaign.get("status") == "COMPLETED",
                campaign.get("status"),
                "COMPLETED",
                "forward-test target not completed",
            ),
            "closed_paper_trades": _check(
                closed_paper_trades >= self.config.require_min_closed_paper_trades,
                closed_paper_trades,
                self.config.require_min_closed_paper_trades,
                "closed paper trades below readiness minimum",
            ),
            "recorded_candles": _check(
                recorded_candles >= self.config.require_min_recorded_candles,
                recorded_candles,
                self.config.require_min_recorded_candles,
                "recorded candles below readiness minimum",
            ),
            "forward_tested_days": _check(
                forward_days >= self.config.require_min_forward_days,
                forward_days,
                self.config.require_min_forward_days,
                "forward-tested days below readiness minimum",
            ),
            "operator_ok": _check(
                operator_ok or not self.config.require_operator_ok,
                operator_ok,
                True,
                "operator summary not ok",
            ),
            "market_quality_ok": _check(
                market_quality_ok or not self.config.require_market_quality_ok,
                market_quality_ok,
                True,
                "market quality not ok",
            ),
            "no_open_commands": _check(
                open_commands == 0 or not self.config.require_no_open_commands,
                open_commands,
                0,
                "open commands present",
            ),
            "no_open_paper_trades": _check(
                open_paper_trades == 0 or not self.config.require_no_open_paper_trades,
                open_paper_trades,
                0,
                "open paper trades present",
            ),
            "ea_live_trading_disabled_now": _check(
                ea_live_disabled or not self.config.require_ea_live_trading_disabled_now,
                ea_live_disabled,
                True,
                "EA live trading is not confirmed disabled",
            ),
            "live_arming_disabled_by_config": _check(
                not self.config.allow_live_arming,
                self.config.allow_live_arming,
                False,
                "live arming is enabled by config",
            ),
            "live_execution_disabled_by_config": _check(
                not self.config.allow_live_execution,
                self.config.allow_live_execution,
                False,
                "live execution is enabled by config",
            ),
            "command_queueing_disabled_by_config": _check(
                not self.config.allow_command_queueing,
                self.config.allow_command_queueing,
                False,
                "command queueing is enabled by config",
            ),
        }
        if not self.config.enabled:
            checks["live_readiness_enabled"] = _check(False, False, True, "live readiness layer disabled")
        if self.config.mode != "READINESS_ONLY":
            checks["readiness_only_mode"] = _check(False, self.config.mode, "READINESS_ONLY", "live readiness mode is not READINESS_ONLY")

        blocking_reasons = [check["reason"] for check in checks.values() if not check["passed"]]
        warnings = _warnings(backtest, research, journal, ai_review, long_forward)
        score = _score(checks)
        status = _status(blocking_reasons, score)

        return LiveReadinessReport(
            symbol=self.config.symbol,
            mode=self.config.mode,
            status=status,
            live_arming_allowed=False,
            live_execution_allowed=False,
            score=score,
            checks=checks,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            manual_requirements=build_manual_checklist(self.config),
            micro_live_plan=build_micro_live_plan(self.config),
            safety=SAFETY.copy(),
        )


class LiveReadinessStore:
    def __init__(self, data_dir: str | Path = "data", config: LiveReadinessConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or LiveReadinessConfig()
        self.report_file = self.data_dir / "live_readiness_report.json"

    def status(self) -> dict[str, Any]:
        latest = self.latest()
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "mode": self.config.mode,
            "latest_exists": bool(latest),
            "latest": latest.model_dump() if latest else None,
            "config": self.config.model_dump(),
            "safety": SAFETY.copy(),
        }

    def latest(self) -> LiveReadinessReport | None:
        data = self._read_dict(self.report_file)
        return LiveReadinessReport(**data) if data else None

    def evaluate(self, inputs: dict[str, Any]) -> LiveReadinessReport:
        report = LiveReadinessEvaluator(self.config).evaluate(inputs)
        self.save(report)
        return report

    def save(self, report: LiveReadinessReport) -> LiveReadinessReport:
        self.report_file.write_text(json.dumps(report.model_dump(), indent=2, default=str), encoding="utf-8")
        return report

    def reset(self) -> None:
        self.report_file.write_text("{}", encoding="utf-8")

    def manual_checklist(self) -> dict[str, Any]:
        return {
            "symbol": self.config.symbol,
            "mode": self.config.mode,
            "items": build_manual_checklist(self.config),
            "safety": SAFETY.copy(),
        }

    def read_inputs(self, operator_status: dict[str, Any], operator_summary: dict[str, Any]) -> dict[str, Any]:
        candles = self._read_list(self.data_dir / "market_candles_m1.json")
        paper_trades = self._read_list(self.data_dir / "paper_trades.json")
        return {
            "evidence_gate_report": self._read_dict(self.data_dir / "evidence_gate_report.json"),
            "forward_test_status": self._wrap_campaign(self._read_dict(self.data_dir / "forward_test_campaign.json")),
            "long_forward_test_status": self._read_dict(self.data_dir / "long_forward_test_status.json"),
            "operator_status": operator_status,
            "operator_summary": operator_summary,
            "market_quality": self._read_dict(self.data_dir / "market_quality.json"),
            "paper_analytics": self._read_dict(self.data_dir / "paper_performance_report.json"),
            "backtest_report": self._read_dict(self.data_dir / "backtest_report.json"),
            "research_sweep": self._read_dict(self.data_dir / "research_parameter_sweep.json"),
            "journal_status": operator_status.get("journal") if isinstance(operator_status.get("journal"), dict) else {},
            "ai_review_report": _latest(self._read_list(self.data_dir / "ai_review_reports.json")),
            "command_lifecycle_open_commands": _as_dict(operator_status.get("commands")).get("open") or [],
            "latest_snapshot": self._read_dict(self.data_dir / "latest_snapshot.json"),
            "recorded_candles": len(candles),
            "forward_days": _days_observed(paper_trades, self._read_list(self.data_dir / "context_snapshots.json")),
            "open_command_count": _first_int(_as_dict(operator_status.get("commands")).get("open_count")),
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

    def _wrap_campaign(self, campaign: dict[str, Any]) -> dict[str, Any]:
        return {"campaign": campaign} if campaign else {}


def _check(passed: bool, value: Any, required: Any, reason: str) -> dict[str, Any]:
    return {"passed": bool(passed), "value": value, "required": required, "reason": reason}


def _score(checks: dict[str, dict[str, Any]]) -> float:
    if not checks:
        return 0.0
    return round(sum(1 for check in checks.values() if check.get("passed")) / len(checks), 6)


def _status(blocking_reasons: list[str], score: float) -> str:
    if not blocking_reasons:
        return "READY_FOR_MANUAL_REVIEW"
    if score >= 0.70:
        return "PAPER_ONLY"
    return "BLOCKED"


def _warnings(
    backtest: dict[str, Any],
    research: dict[str, Any],
    journal: dict[str, Any],
    ai_review: dict[str, Any],
    long_forward: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(str(item) for item in backtest.get("warnings") or [])
    warnings.extend(str(item) for item in research.get("warnings") or [])
    if not journal:
        warnings.append("journal status unavailable")
    if not ai_review:
        warnings.append("AI review report unavailable")
    if long_forward and long_forward.get("running"):
        warnings.append("long forward-test is currently running")
    return list(dict.fromkeys(warnings))


def _ea_live_trading_disabled(operator_status: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    safety = _as_dict(operator_status.get("safety"))
    seen = safety.get("ea_broker_execution_seen")
    if seen is not None:
        return seen is False
    raw = _find_key(snapshot, {"aurix_broker_execution", "broker_execution_enabled", "ea_broker_execution"})
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw is False
    return str(raw).strip().lower() in {"false", "0", "no", "disabled"}


def _find_key(value: Any, names: set[str]) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).replace("_", "").lower() in names:
                return item
        for item in value.values():
            found = _find_key(item, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_key(item, names)
            if found is not None:
                return found
    return None


def _days_observed(paper_trades: list[dict[str, Any]], contexts: list[dict[str, Any]]) -> int:
    days: set[str] = set()
    for item in [*paper_trades, *contexts]:
        value = item.get("opened_at") or item.get("created_at") or item.get("snapshot_updated_at")
        parsed = _parse_datetime(value)
        if parsed:
            days.add(parsed.date().isoformat())
    return len(days)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest(items: list[dict[str, Any]]) -> dict[str, Any]:
    return items[-1] if items else {}


def _first_int(*values: Any) -> int:
    for value in values:
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
