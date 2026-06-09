from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import EvidenceMonitorConfig
from .models import EvidenceGrowthReport
from .progress import ratio, weighted_progress


SAFETY = {
    "monitor_only": True,
    "live_execution_allowed": False,
    "live_arming_allowed": False,
    "mt5_commands_queued": False,
    "ea_settings_modified": False,
    "external_llm_used": False,
    "strategy_config_mutated": False,
    "readiness_config_modified": False,
}


class EvidenceGrowthMonitor:
    def __init__(self, config: EvidenceMonitorConfig):
        self.config = config

    def evaluate(self, inputs: dict[str, Any]) -> EvidenceGrowthReport:
        live_readiness = _as_dict(inputs.get("live_readiness_report"))
        evidence = _as_dict(inputs.get("evidence_gate_report"))
        forward = _as_dict(inputs.get("forward_test_status"))
        long_forward = _as_dict(inputs.get("long_forward_test_status"))
        paper_analytics = _as_dict(inputs.get("paper_analytics"))
        paper_status = _as_dict(inputs.get("paper_status"))
        market_recorder = _as_dict(inputs.get("market_recorder_status"))
        operator_status = _as_dict(inputs.get("operator_status"))
        operator_summary = _as_dict(inputs.get("operator_summary"))
        market_quality = _as_dict(inputs.get("market_quality"))
        journal_status = _as_dict(inputs.get("journal_status"))
        commands = _as_dict(operator_status.get("commands"))
        campaign = _as_dict(forward.get("campaign"))

        closed_paper_trades = _first_int(
            paper_analytics.get("closed_trades"),
            campaign.get("closed_paper_trades"),
            paper_status.get("closed_trades"),
            operator_summary.get("paper_closed_trades"),
        )
        recorded_candles = _first_int(
            campaign.get("recorded_candles"),
            campaign.get("candles_recorded"),
            long_forward.get("recorded_candles"),
            market_recorder.get("candles_recorded"),
            market_recorder.get("candle_count"),
            inputs.get("recorded_candles"),
        )
        forward_days = _first_int(
            campaign.get("days_observed"),
            long_forward.get("days_observed"),
            inputs.get("forward_days"),
        )
        open_commands = _first_int(commands.get("open_count"), inputs.get("open_command_count"))
        open_paper_trades = _first_int(paper_status.get("open_trades"), operator_summary.get("paper_open_count"))
        evidence_status = str(evidence.get("status") or "")
        evidence_ok = _evidence_meets_target(evidence_status, self.config.target_evidence_gate_status)
        market_quality_ok = bool(operator_summary.get("market_quality_ok") or market_quality.get("ok"))
        operator_ok = bool(operator_summary.get("ok"))
        readiness_safety_ok = _live_readiness_safety_limited(live_readiness)

        targets = {
            "closed_paper_trades": self.config.target_closed_paper_trades,
            "recorded_candles": self.config.target_recorded_candles,
            "forward_tested_days": self.config.target_forward_days,
            "evidence_gate_status": self.config.target_evidence_gate_status,
            "open_commands": 0,
            "open_paper_trades_for_completion": 0,
        }
        current = {
            "closed_paper_trades": closed_paper_trades,
            "recorded_candles": recorded_candles,
            "forward_tested_days": forward_days,
            "evidence_gate_status": evidence_status or None,
            "open_commands": open_commands,
            "open_paper_trades": open_paper_trades,
            "market_quality_ok": market_quality_ok,
            "operator_ok": operator_ok,
            "live_readiness_status": live_readiness.get("status"),
            "live_readiness_arming_allowed": bool(live_readiness.get("live_arming_allowed")),
            "live_readiness_execution_allowed": bool(live_readiness.get("live_execution_allowed")),
            "journal_available": bool(journal_status),
        }
        checkpoints = {
            "closed_paper_trades": _checkpoint(
                ratio(closed_paper_trades, self.config.target_closed_paper_trades),
                closed_paper_trades,
                self.config.target_closed_paper_trades,
                closed_paper_trades >= self.config.target_closed_paper_trades,
            ),
            "recorded_candles": _checkpoint(
                ratio(recorded_candles, self.config.target_recorded_candles),
                recorded_candles,
                self.config.target_recorded_candles,
                recorded_candles >= self.config.target_recorded_candles,
            ),
            "forward_tested_days": _checkpoint(
                ratio(forward_days, self.config.target_forward_days),
                forward_days,
                self.config.target_forward_days,
                forward_days >= self.config.target_forward_days,
            ),
            "evidence_gate_status": _checkpoint(1.0 if evidence_ok else 0.0, evidence_status or None, self.config.target_evidence_gate_status, evidence_ok),
            "command_cleanliness": _checkpoint(1.0 if open_commands == 0 else 0.0, open_commands, 0, open_commands == 0),
            "market_quality": _checkpoint(1.0 if market_quality_ok else 0.0, market_quality_ok, True, market_quality_ok),
            "operator_status": _checkpoint(1.0 if operator_ok else 0.0, operator_ok, True, operator_ok),
        }
        overall_progress = weighted_progress(checkpoints)
        missing = _missing_requirements(current, checkpoints, self.config)
        blocking = _blocking_reasons(current, self.config, readiness_safety_ok)
        warnings = _warnings(live_readiness, evidence, forward, long_forward, journal_status)
        status = _status(inputs, overall_progress, missing, blocking, self.config)

        return EvidenceGrowthReport(
            symbol=self.config.symbol,
            mode=self.config.mode,
            status=status,
            overall_progress=overall_progress,
            targets=targets,
            current=current,
            deltas={
                "closed_paper_trades_remaining": max(self.config.target_closed_paper_trades - closed_paper_trades, 0),
                "recorded_candles_remaining": max(self.config.target_recorded_candles - recorded_candles, 0),
                "forward_days_remaining": max(self.config.target_forward_days - forward_days, 0),
            },
            checkpoints=checkpoints,
            missing_requirements=missing,
            blocking_reasons=blocking,
            warnings=warnings,
            recommendations=_recommendations(missing, blocking, self.config),
            safety=SAFETY.copy(),
        )


class EvidenceMonitorStore:
    def __init__(self, data_dir: str | Path = "data", config: EvidenceMonitorConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or EvidenceMonitorConfig()
        self.report_file = self.data_dir / "evidence_growth_report.json"
        self.history_file = self.data_dir / "evidence_growth_history.jsonl"

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

    def latest(self) -> EvidenceGrowthReport | None:
        data = self._read_dict(self.report_file)
        return EvidenceGrowthReport(**data) if data else None

    def evaluate(self, inputs: dict[str, Any]) -> EvidenceGrowthReport:
        report = EvidenceGrowthMonitor(self.config).evaluate(inputs)
        self.save(report)
        if self.config.write_history:
            self.append_history(report)
        return report

    def save(self, report: EvidenceGrowthReport) -> EvidenceGrowthReport:
        self.report_file.write_text(json.dumps(report.model_dump(), indent=2, default=str), encoding="utf-8")
        return report

    def append_history(self, report: EvidenceGrowthReport) -> None:
        entry = {
            "id": report.id,
            "generated_at": report.generated_at,
            "status": report.status,
            "overall_progress": report.overall_progress,
            "closed_paper_trades": report.current.get("closed_paper_trades"),
            "recorded_candles": report.current.get("recorded_candles"),
            "forward_tested_days": report.current.get("forward_tested_days"),
            "missing_count": len(report.missing_requirements),
            "blocking_count": len(report.blocking_reasons),
        }
        lines = self.history()
        lines.append(entry)
        limit = max(int(self.config.snapshot_history_limit or 0), 1)
        lines = lines[-limit:]
        self.history_file.write_text("".join(json.dumps(item, default=str) + "\n" for item in lines), encoding="utf-8")

    def history(self, limit: int | None = None) -> list[dict[str, Any]]:
        if not self.history_file.exists():
            return []
        items: list[dict[str, Any]] = []
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
        paper_trades = self._read_list(self.data_dir / "paper_trades.json")
        contexts = self._read_list(self.data_dir / "context_snapshots.json")
        candles = self._read_list(self.data_dir / "market_candles_m1.json")
        return {
            "live_readiness_report": self._read_dict(self.data_dir / "live_readiness_report.json"),
            "evidence_gate_report": self._read_dict(self.data_dir / "evidence_gate_report.json"),
            "forward_test_status": self._wrap_campaign(self._read_dict(self.data_dir / "forward_test_campaign.json")),
            "long_forward_test_status": self._read_dict(self.data_dir / "long_forward_test_status.json"),
            "paper_analytics": self._read_dict(self.data_dir / "paper_performance_report.json"),
            "paper_trades": paper_trades,
            "paper_status": operator_status.get("paper") if isinstance(operator_status.get("paper"), dict) else {},
            "market_recorder_status": _as_dict(_as_dict(operator_status.get("market")).get("recorder")),
            "operator_status": operator_status,
            "operator_summary": operator_summary,
            "market_quality": self._read_dict(self.data_dir / "market_quality.json"),
            "command_lifecycle_open_commands": _as_dict(operator_status.get("commands")).get("open") or [],
            "journal_status": operator_status.get("journal") if isinstance(operator_status.get("journal"), dict) else {},
            "recorded_candles": len(candles),
            "forward_days": _days_observed(paper_trades, contexts),
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


def _checkpoint(progress: float, current: Any, target: Any, complete: bool) -> dict[str, Any]:
    return {"progress": progress, "current": current, "target": target, "complete": bool(complete)}


def _evidence_meets_target(status: str, target: str) -> bool:
    if not status or status == "BLOCKED":
        return False
    if target == "ELIGIBLE":
        return status in {"ELIGIBLE", "ELIGIBLE_PAPER_ONLY", "READY_FOR_MANUAL_REVIEW"}
    return status == target


def _live_readiness_safety_limited(report: dict[str, Any]) -> bool:
    if not report:
        return True
    safety = _as_dict(report.get("safety"))
    return (
        report.get("live_arming_allowed") is False
        and report.get("live_execution_allowed") is False
        and safety.get("live_arming_allowed") is False
        and safety.get("live_execution_allowed") is False
        and safety.get("mt5_commands_queued") is False
        and safety.get("ea_settings_modified") is False
        and safety.get("strategy_config_mutated") is False
    )


def _missing_requirements(current: dict[str, Any], checkpoints: dict[str, dict[str, Any]], config: EvidenceMonitorConfig) -> list[str]:
    missing: list[str] = []
    if not checkpoints["closed_paper_trades"]["complete"]:
        missing.append(f"closed paper trades below target: {current['closed_paper_trades']}/{config.target_closed_paper_trades}")
    if not checkpoints["recorded_candles"]["complete"]:
        missing.append(f"recorded candles below target: {current['recorded_candles']}/{config.target_recorded_candles}")
    if not checkpoints["forward_tested_days"]["complete"]:
        missing.append(f"forward-tested days below target: {current['forward_tested_days']}/{config.target_forward_days}")
    if not checkpoints["evidence_gate_status"]["complete"]:
        missing.append("evidence gate has not met target status")
    if config.require_market_quality_ok and not current["market_quality_ok"]:
        missing.append("market quality is not ok")
    if config.require_operator_ok and not current["operator_ok"]:
        missing.append("operator summary is not ok")
    if config.require_no_open_paper_trades_for_completion and current["open_paper_trades"] > 0:
        missing.append("open paper trades present")
    return missing


def _blocking_reasons(current: dict[str, Any], config: EvidenceMonitorConfig, readiness_safety_ok: bool) -> list[str]:
    reasons: list[str] = []
    if not config.enabled:
        reasons.append("evidence monitor disabled")
    if config.mode != "MONITOR_ONLY":
        reasons.append("evidence monitor mode is not MONITOR_ONLY")
    if config.allow_live_arming:
        reasons.append("live arming is enabled by evidence monitor config")
    if config.allow_live_execution:
        reasons.append("live execution is enabled by evidence monitor config")
    if config.allow_command_queueing:
        reasons.append("command queueing is enabled by evidence monitor config")
    if config.require_no_open_commands and current["open_commands"] > 0:
        reasons.append("open commands present")
    if config.require_live_readiness_blocked_or_manual_review_only and not readiness_safety_ok:
        reasons.append("live readiness safety flags are unsafe")
    return reasons


def _warnings(
    live_readiness: dict[str, Any],
    evidence: dict[str, Any],
    forward: dict[str, Any],
    long_forward: dict[str, Any],
    journal_status: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(str(item) for item in live_readiness.get("warnings") or [])
    warnings.extend(str(item) for item in evidence.get("warnings") or [])
    warnings.extend(str(item) for item in _as_dict(forward.get("campaign")).get("warnings") or [])
    if long_forward.get("running"):
        warnings.append("long forward-test is currently running")
    if not journal_status:
        warnings.append("journal status unavailable")
    return list(dict.fromkeys(warnings))


def _recommendations(missing: list[str], blocking: list[str], config: EvidenceMonitorConfig) -> list[str]:
    recommendations: list[str] = []
    if any("closed paper trades" in item for item in missing):
        recommendations.append(f"continue paper testing until {config.target_closed_paper_trades} closed trades are available")
    if any("recorded candles" in item for item in missing):
        recommendations.append(f"continue market recording until {config.target_recorded_candles} candles are available")
    if any("forward-tested days" in item for item in missing):
        recommendations.append(f"continue forward testing until {config.target_forward_days} observed days are available")
    if any("evidence gate" in item for item in missing):
        recommendations.append("resolve evidence gate blockers before readiness review")
    if blocking:
        recommendations.append("resolve blocking safety conditions before treating progress as review-ready")
    recommendations.append("keep live arming and execution disabled; this monitor only feeds future manual readiness review")
    return list(dict.fromkeys(recommendations))


def _status(
    inputs: dict[str, Any],
    overall_progress: float,
    missing: list[str],
    blocking: list[str],
    config: EvidenceMonitorConfig,
) -> str:
    if blocking:
        return "BLOCKED"
    if not _has_useful_evidence(inputs):
        return "NO_DATA"
    if not missing and config.enabled and config.mode == "MONITOR_ONLY":
        return "READY_FOR_READINESS_REVIEW"
    if overall_progress >= 0.50:
        return "IMPROVING"
    return "COLLECTING"


def _has_useful_evidence(inputs: dict[str, Any]) -> bool:
    return any(
        [
            bool(_as_dict(inputs.get("live_readiness_report"))),
            bool(_as_dict(inputs.get("evidence_gate_report"))),
            bool(_as_dict(inputs.get("forward_test_status"))),
            bool(_as_dict(inputs.get("paper_analytics"))),
            bool(inputs.get("recorded_candles")),
            bool(inputs.get("forward_days")),
        ]
    )


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
