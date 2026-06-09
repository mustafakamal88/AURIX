from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AIReviewConfig
from .models import AIReviewReport


class AIReviewStore:
    def __init__(self, data_dir: str | Path = "data", config: AIReviewConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or AIReviewConfig()
        self.reports_file = self.data_dir / "ai_review_reports.json"
        self.journal_file = self.data_dir / "journal_entries.json"
        self.analytics_file = self.data_dir / "paper_performance_report.json"
        self.context_file = self.data_dir / "context_snapshots.json"
        self.market_quality_file = self.data_dir / "market_quality.json"
        self.signals_file = self.data_dir / "strategy_signals.json"
        self.trades_file = self.data_dir / "paper_trades.json"
        if not self.reports_file.exists():
            self.reports_file.write_text("[]", encoding="utf-8")

    def status(self) -> dict[str, Any]:
        reports = self.list_reports()
        latest = reports[-1] if reports else None
        return {
            "enabled": self.config.enabled,
            "mode": self.config.mode,
            "allow_external_llm": self.config.allow_external_llm,
            "reports_count": len(reports),
            "latest_summary": latest.get("summary") if latest else None,
            "latest_action_items_count": len(latest.get("action_items") or []) if latest else 0,
            "latest_report_id": latest.get("id") if latest else None,
            "config": self.config.model_dump(),
        }

    def list_reports(self) -> list[dict[str, Any]]:
        return self._read_list(self.reports_file)

    def latest(self) -> dict[str, Any] | None:
        reports = self.list_reports()
        return reports[-1] if reports else None

    def save(self, report: AIReviewReport) -> AIReviewReport:
        reports = self.list_reports()
        reports.append(report.model_dump())
        self.reports_file.write_text(json.dumps(reports[-100:], indent=2, default=str), encoding="utf-8")
        return report

    def reset(self) -> None:
        self.reports_file.write_text("[]", encoding="utf-8")

    def read_inputs(self) -> dict[str, Any]:
        contexts = self._read_list(self.context_file)
        return {
            "journal_entries": self._read_list(self.journal_file)[-self.config.max_journal_entries :] if self.config.include_journal else [],
            "analytics_report": self._read_dict(self.analytics_file) if self.config.include_analytics else {},
            "latest_context": contexts[-1] if contexts and self.config.include_context else {},
            "market_quality": self._read_dict(self.market_quality_file) if self.config.include_market_quality else {},
            "signals": self._read_list(self.signals_file)[-self.config.max_signals :],
            "paper_trades": self._read_list(self.trades_file)[-self.config.max_paper_trades :],
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


class AIReviewTemplateReviewer:
    def __init__(self, config: AIReviewConfig):
        self.config = config

    def generate(self, inputs: dict[str, Any]) -> AIReviewReport:
        journal_entries = _as_list(inputs.get("journal_entries"))
        analytics = _as_dict(inputs.get("analytics_report"))
        latest_context = _as_dict(inputs.get("latest_context"))
        market_quality = _as_dict(inputs.get("market_quality"))
        signals = _as_list(inputs.get("signals"))
        paper_trades = _as_list(inputs.get("paper_trades"))
        closed_trades = int(analytics.get("closed_trades") or 0)
        total_trades = int(analytics.get("total_trades") or len(paper_trades))
        session_blocked = [entry for entry in journal_entries if entry.get("classification") == "SESSION_BLOCKED"]
        warnings = [str(warning) for warning in analytics.get("warnings") or []]

        performance = self._performance_observations(analytics, closed_trades)
        behaviour = self._behaviour_observations(journal_entries, session_blocked)
        strategy = self._strategy_observations(signals, paper_trades, total_trades)
        risk = ["Risk posture remains paper-only; no live execution recommendation is made."]
        data_quality = self._data_quality_observations(market_quality)
        mistakes = self._mistake_patterns(journal_entries, warnings)
        positives = self._positive_patterns(session_blocked, market_quality)
        actions = self._action_items(total_trades, closed_trades, warnings)
        blocked = [
            "Live trading review is blocked until a separate explicit approval process exists.",
            "Risk increases are blocked by design in this review layer.",
            "Strategy mutation is blocked; this report is explanatory only.",
        ]

        summary = self._summary(closed_trades, analytics, warnings)
        return AIReviewReport(
            symbol=self.config.symbol,
            mode=self.config.mode,
            period="latest",
            summary=summary,
            performance_observations=performance,
            behaviour_observations=behaviour,
            strategy_observations=strategy,
            risk_observations=risk,
            data_quality_observations=data_quality,
            mistake_patterns=mistakes,
            positive_patterns=positives,
            action_items=actions,
            blocked_items=blocked,
            safety={
                "review_only": True,
                "no_execution": True,
                "no_strategy_mutation": True,
                "external_llm_used": False,
                "commands_queued": False,
            },
            source_counts={
                "journal_entries": len(journal_entries),
                "signals": len(signals),
                "paper_trades": len(paper_trades),
                "closed_paper_trades": closed_trades,
            },
        )

    def _summary(self, closed_trades: int, analytics: dict[str, Any], warnings: list[str]) -> str:
        if closed_trades <= 0:
            return "Not enough performance data yet: no closed paper trades are available for review."
        return (
            "Paper review generated from closed trades: "
            f"win_rate={analytics.get('win_rate', 0)}, total_r={analytics.get('total_r', 0)}, "
            f"expectancy_r={analytics.get('expectancy_r', 0)}, warnings={len(warnings)}."
        )

    def _performance_observations(self, analytics: dict[str, Any], closed_trades: int) -> list[str]:
        if closed_trades <= 0:
            return ["There is not enough performance data yet because no paper trades are closed."]
        return [
            f"Closed trades={closed_trades}.",
            f"Win rate={analytics.get('win_rate', 0)}.",
            f"Total R={analytics.get('total_r', 0)}.",
            f"Expectancy R={analytics.get('expectancy_r', 0)}.",
            f"Max consecutive losses={analytics.get('max_consecutive_losses', 0)}.",
        ]

    def _behaviour_observations(self, entries: list[dict[str, Any]], session_blocked: list[dict[str, Any]]) -> list[str]:
        observations = [f"Journal entries reviewed={len(entries)}."]
        if len(session_blocked) >= 2:
            observations.append("Multiple SESSION_BLOCKED signals show the strategy is respecting session rules.")
        elif session_blocked:
            observations.append("A SESSION_BLOCKED signal was detected; session filtering is active.")
        return observations

    def _strategy_observations(self, signals: list[dict[str, Any]], trades: list[dict[str, Any]], total_trades: int) -> list[str]:
        observations = [f"Signals reviewed={len(signals)}.", f"Paper trades reviewed={len(trades)}."]
        if total_trades == 0:
            observations.append("No paper trades exist yet, so execution-quality conclusions are premature.")
        return observations

    def _data_quality_observations(self, market_quality: dict[str, Any]) -> list[str]:
        if market_quality.get("ok"):
            return ["Market quality is currently acceptable based on the latest quality report."]
        reasons = market_quality.get("reasons") or ["market quality report missing or not ok"]
        return [f"Market quality warning: {reason}" for reason in reasons]

    def _mistake_patterns(self, entries: list[dict[str, Any]], warnings: list[str]) -> list[str]:
        patterns = []
        flag_counts: dict[str, int] = {}
        for entry in entries:
            for flag in entry.get("mistake_flags") or []:
                if flag != "NONE":
                    flag_counts[str(flag)] = flag_counts.get(str(flag), 0) + 1
        patterns.extend(f"{flag} seen {count} time(s)" for flag, count in sorted(flag_counts.items()))
        patterns.extend(f"Analytics warning: {warning}" for warning in warnings)
        return patterns or ["No repeated mistake pattern is established yet."]

    def _positive_patterns(self, session_blocked: list[dict[str, Any]], market_quality: dict[str, Any]) -> list[str]:
        patterns = []
        if session_blocked:
            patterns.append("Session blocking behavior is visible in journal evidence.")
        if market_quality.get("ok"):
            patterns.append("Data quality is acceptable for paper review.")
        return patterns or ["No positive pattern is established yet."]

    def _action_items(self, total_trades: int, closed_trades: int, warnings: list[str]) -> list[str]:
        items = []
        if total_trades == 0:
            items.append("Continue paper-forward testing during active sessions.")
        elif closed_trades == 0:
            items.append("Continue collecting paper outcomes until trades close before judging performance.")
        else:
            items.append("Review closed paper trades by session and regime before changing any strategy rule.")
        if warnings:
            items.append("Resolve analytics warnings before relying on performance conclusions.")
        return items


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
