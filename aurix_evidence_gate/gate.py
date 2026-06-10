from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import EvidenceGateConfig
from .models import EvidenceGateReport


SAFETY = {
    "live_trading_enabled": False,
    "live_readiness_allowed_by_config": False,
    "no_mt5_execution": True,
    "commands_queued": False,
    "external_llm_used": False,
    "config_mutated": False,
}


class EvidenceGate:
    def __init__(self, config: EvidenceGateConfig):
        self.config = config

    def evaluate(self, inputs: dict[str, Any]) -> EvidenceGateReport:
        paper = _as_dict(inputs.get("paper_analytics"))
        backtest = _as_dict(inputs.get("backtest_report"))
        research = _as_dict(inputs.get("research_report"))
        market = _as_dict(inputs.get("market_status"))
        operator_status = _as_dict(inputs.get("operator_status"))
        operator_summary = _as_dict(inputs.get("operator_summary"))
        journal_entries = _as_list(inputs.get("journal_entries"))
        ai_review = _as_dict(inputs.get("ai_review_report"))

        paper_closed = _as_int(paper.get("closed_trades"))
        backtest_trades = _as_int(backtest.get("trades"))
        recorded_candles = _as_int(market.get("candle_count"))
        expectancy = _first_float(paper.get("expectancy_r"), backtest.get("expectancy_r"))
        profit_factor = _first_float(paper.get("profit_factor"), backtest.get("profit_factor"))
        max_losses = _max_known_loss_streak(paper, backtest)
        profitable_sessions = _profitable_sessions(paper)
        forward_days = _forward_test_days(_as_list(inputs.get("paper_trades")))
        operator_ok = bool(operator_summary.get("ok"))
        market_quality_ok = bool(operator_summary.get("market_quality_ok") or _as_dict(market.get("quality")).get("ok"))
        open_commands = _as_int(_as_dict(operator_status.get("commands")).get("open_count"))
        live_trading_disabled = _live_trading_disabled(operator_status)

        checks = {
            "closed_paper_trades": _check(
                paper_closed >= self.config.minimum_closed_paper_trades,
                paper_closed,
                self.config.minimum_closed_paper_trades,
                "closed paper trades below minimum",
            ),
            "backtest_trades": _check(
                backtest_trades >= self.config.minimum_backtest_trades,
                backtest_trades,
                self.config.minimum_backtest_trades,
                "backtest trades below minimum",
            ),
            "recorded_candles": _check(
                recorded_candles >= self.config.minimum_recorded_candles,
                recorded_candles,
                self.config.minimum_recorded_candles,
                "recorded candles below minimum",
            ),
            "profitable_sessions": _check(
                profitable_sessions >= self.config.minimum_profitable_sessions,
                profitable_sessions,
                self.config.minimum_profitable_sessions,
                "profitable sessions below minimum",
            ),
            "expectancy_r": _check(
                expectancy is not None and expectancy >= self.config.minimum_expectancy_r,
                expectancy,
                self.config.minimum_expectancy_r,
                "expectancy below minimum",
            ),
            "profit_factor": _check(
                profit_factor is not None and profit_factor >= self.config.minimum_profit_factor,
                profit_factor,
                self.config.minimum_profit_factor,
                "profit factor below minimum",
            ),
            "max_consecutive_losses": _check(
                max_losses is not None and max_losses <= self.config.maximum_consecutive_losses,
                max_losses,
                self.config.maximum_consecutive_losses,
                "maximum consecutive losses exceeded or unavailable",
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
            "live_trading_disabled": _check(
                live_trading_disabled or not self.config.require_live_trading_disabled,
                live_trading_disabled,
                True,
                "live trading is not confirmed disabled",
            ),
            "forward_tested_days": _check(
                forward_days >= self.config.minimum_days_forward_tested,
                forward_days,
                self.config.minimum_days_forward_tested,
                "forward-tested days below minimum",
            ),
        }
        if not self.config.enabled:
            checks["gate_enabled"] = _check(False, False, True, "evidence gate disabled")

        blocking_reasons = [check["reason"] for check in checks.values() if not check["passed"]]
        warnings = _warnings(paper, backtest, research, journal_entries, ai_review, operator_summary)
        score = _score(checks)
        status = _status(blocking_reasons, score)
        recommendations = _recommendations(checks, self.config)
        safety = SAFETY.copy()
        safety["live_readiness_allowed_by_config"] = bool(self.config.allow_live_readiness)
        safety["live_trading_enabled"] = not live_trading_disabled

        return EvidenceGateReport(
            symbol=self.config.symbol,
            status=status,
            live_ready=False,
            score=score,
            checks=checks,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            data_summary={
                "closed_paper_trades": paper_closed,
                "backtest_trades": backtest_trades,
                "recorded_candles": recorded_candles,
                "profitable_sessions": profitable_sessions,
                "expectancy_r": expectancy,
                "profit_factor": profit_factor,
                "max_consecutive_losses": max_losses,
                "forward_tested_days": forward_days,
                "research_total_variants": _as_int(research.get("total_variants")),
                "journal_entries": len(journal_entries),
                "ai_review_available": bool(ai_review),
            },
            recommendations=recommendations,
            safety=safety,
        )


class EvidenceGateStore:
    def __init__(self, data_dir: str | Path = "data", config: EvidenceGateConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or EvidenceGateConfig()
        self.report_file = self.data_dir / "evidence_gate_report.json"

    def status(self) -> dict[str, Any]:
        latest = self.latest()
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "latest_exists": self.report_file.exists(),
            "latest": latest.model_dump() if latest else None,
            "config": self.config.model_dump(),
            "safety": SAFETY.copy(),
        }

    def evaluate(self, inputs: dict[str, Any]) -> EvidenceGateReport:
        report = EvidenceGate(self.config).evaluate(inputs)
        self.save(report)
        return report

    def save(self, report: EvidenceGateReport) -> EvidenceGateReport:
        self.report_file.write_text(json.dumps(report.model_dump(), indent=2, default=str), encoding="utf-8")
        return report

    def latest(self) -> EvidenceGateReport | None:
        data = self._read_dict(self.report_file)
        return EvidenceGateReport(**data) if data else None

    def reset(self) -> None:
        self.report_file.write_text("{}", encoding="utf-8")

    def read_inputs(self, operator_status: dict[str, Any], operator_summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "paper_analytics": self._read_dict(self.data_dir / "paper_performance_report.json"),
            "backtest_report": self._read_dict(self.data_dir / "backtest_report.json"),
            "research_report": self._read_dict(self.data_dir / "research_parameter_sweep.json"),
            "market_status": {
                "candle_count": len(self._read_list(self.data_dir / "market_candles_m1.json")),
                "quality": self._read_dict(self.data_dir / "market_quality.json"),
            },
            "operator_status": operator_status,
            "operator_summary": operator_summary,
            "journal_entries": self._read_list(self.data_dir / "journal_entries.json"),
            "ai_review_report": _latest(self._read_list(self.data_dir / "ai_review_reports.json")),
            "paper_trades": self._read_list(self.data_dir / "paper_trades.json"),
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


def _check(passed: bool, value: Any, required: Any, reason: str) -> dict[str, Any]:
    return {"passed": bool(passed), "value": value, "required": required, "reason": reason}


def _score(checks: dict[str, dict[str, Any]]) -> float:
    if not checks:
        return 0.0
    passed = sum(1 for check in checks.values() if check.get("passed"))
    return round(passed / len(checks), 6)


def _status(blocking_reasons: list[str], score: float) -> str:
    if not blocking_reasons:
        return "ELIGIBLE_PAPER_ONLY"
    if score >= 0.70:
        return "WATCHLIST"
    return "BLOCKED"


def _recommendations(checks: dict[str, dict[str, Any]], config: EvidenceGateConfig) -> list[str]:
    recommendations = []
    if not checks["closed_paper_trades"]["passed"]:
        recommendations.append(f"Continue paper testing until at least {config.minimum_closed_paper_trades} closed paper trades exist.")
    if not checks["backtest_trades"]["passed"]:
        recommendations.append(f"Record and replay enough candles to produce at least {config.minimum_backtest_trades} backtest trades.")
    if not checks["recorded_candles"]["passed"]:
        recommendations.append(f"Continue market recording until at least {config.minimum_recorded_candles} M1 candles exist.")
    if not checks["expectancy_r"]["passed"] or not checks["profit_factor"]["passed"]:
        recommendations.append("Keep the system in research/paper mode until expectancy and profit factor clear evidence thresholds.")
    if not checks["operator_ok"]["passed"]:
        recommendations.append("Resolve operator warnings before considering any readiness review.")
    if not checks["live_trading_disabled"]["passed"]:
        recommendations.append("Confirm live trading remains disabled before continuing evaluation.")
    recommendations.append("Live readiness remains disabled by config; this gate can only return paper-only eligibility.")
    return recommendations


def _warnings(
    paper: dict[str, Any],
    backtest: dict[str, Any],
    research: dict[str, Any],
    journal_entries: list[Any],
    ai_review: dict[str, Any],
    operator_summary: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    warnings.extend(str(item) for item in paper.get("warnings") or [])
    warnings.extend(str(item) for item in backtest.get("warnings") or [])
    warnings.extend(str(item) for item in research.get("warnings") or [])
    warnings.extend(str(item) for item in operator_summary.get("warnings") or [])
    if not journal_entries:
        warnings.append("no journal entries available")
    if not ai_review:
        warnings.append("no AI review report available")
    return list(dict.fromkeys(warnings))


def _profitable_sessions(paper: dict[str, Any]) -> int:
    sessions = _as_dict(paper.get("by_session"))
    count = 0
    for metrics in sessions.values():
        data = _as_dict(metrics)
        if (_as_float(data.get("expectancy_r")) or 0.0) > 0 and (_as_int(data.get("trades"))) > 0:
            count += 1
    return count


def _forward_test_days(trades: list[dict[str, Any]]) -> int:
    days: set[str] = set()
    for trade in trades:
        value = trade.get("opened_at") or trade.get("created_at") or trade.get("entry_time")
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
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _live_trading_disabled(operator_status: dict[str, Any]) -> bool:
    safety = _as_dict(operator_status.get("safety"))
    if safety.get("live_trading_enabled") is not False:
        return False
    if safety.get("ea_broker_execution_seen") is True:
        return False
    return True


def _max_known_loss_streak(paper: dict[str, Any], backtest: dict[str, Any]) -> Optional[int]:
    values = [_as_float(paper.get("max_consecutive_losses")), _as_float(backtest.get("max_consecutive_losses"))]
    known = [int(value) for value in values if value is not None]
    return max(known) if known else None


def _first_float(*values: Any) -> Optional[float]:
    for value in values:
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return None


def _latest(items: list[dict[str, Any]]) -> dict[str, Any]:
    return items[-1] if items else {}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
