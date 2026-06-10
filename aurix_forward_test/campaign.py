from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from aurix_bridge_server.models import utc_now_iso

from .config import ForwardTestConfig
from .models import ForwardTestCampaign
from .report import progress_summary


SAFETY = {
    "paper_only": True,
    "live_trading_allowed": False,
    "no_mt5_execution": True,
    "commands_queued": False,
    "external_llm_used": False,
    "config_mutated": False,
}


class ForwardTestStore:
    def __init__(self, data_dir: str | Path = "data", config: ForwardTestConfig | None = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or ForwardTestConfig()
        self.campaign_file = self.data_dir / "forward_test_campaign.json"

    def status(self) -> dict[str, Any]:
        campaign = self.latest()
        return {
            "enabled": self.config.enabled,
            "symbol": self.config.symbol,
            "mode": self.config.mode,
            "latest_exists": self.campaign_file.exists(),
            "campaign": campaign.model_dump() if campaign else None,
            "config": self.config.model_dump(),
            "safety": SAFETY.copy(),
        }

    def start(self) -> ForwardTestCampaign:
        campaign = self.latest()
        if campaign is None:
            campaign = ForwardTestCampaign(symbol=self.config.symbol, mode=self.config.mode)
        campaign.status = "ACTIVE"
        campaign.last_updated_at = utc_now_iso()
        campaign.safety = SAFETY.copy()
        self.save(campaign)
        return campaign

    def pause(self) -> ForwardTestCampaign:
        campaign = self.latest() or ForwardTestCampaign(symbol=self.config.symbol, mode=self.config.mode)
        campaign.status = "PAUSED"
        campaign.last_updated_at = utc_now_iso()
        campaign.safety = SAFETY.copy()
        self.save(campaign)
        return campaign

    def update(self, inputs: dict[str, Any]) -> ForwardTestCampaign:
        campaign = self.latest() or ForwardTestCampaign(symbol=self.config.symbol, mode=self.config.mode)
        if campaign.status == "NOT_STARTED":
            campaign.status = "ACTIVE"

        paper_trades = _as_list(inputs.get("paper_trades"))
        contexts = _as_list(inputs.get("contexts"))
        candles = _as_list(inputs.get("candles"))
        daemon = _as_dict(inputs.get("daemon_status"))
        operator_summary = _as_dict(inputs.get("operator_summary"))
        evidence = _as_dict(inputs.get("evidence_report"))

        closed = [trade for trade in paper_trades if str(trade.get("status") or "").startswith("CLOSED") or trade.get("status") == "EXPIRED"]
        sessions = sorted(
            {
                str(context.get("session_name"))
                for context in contexts
                if context.get("session_name") in set(self.config.target_sessions)
            }
        )
        values = {
            "days_observed": _days_observed(paper_trades, contexts),
            "sessions_observed": sessions,
            "recorded_candles": len(candles),
            "paper_trades": len(paper_trades),
            "closed_paper_trades": len(closed),
            "daemon_loops": int(daemon.get("loop_count") or 0),
            "operator_ok": bool(operator_summary.get("ok")),
            "evidence_status": evidence.get("status"),
        }

        campaign.days_observed = values["days_observed"]
        campaign.sessions_observed = sessions
        campaign.recorded_candles = values["recorded_candles"]
        campaign.paper_trades = values["paper_trades"]
        campaign.closed_paper_trades = values["closed_paper_trades"]
        campaign.daemon_loops = values["daemon_loops"]
        campaign.operator_ok = values["operator_ok"]
        campaign.evidence_status = values["evidence_status"]
        campaign.progress = progress_summary(self.config, values)
        campaign.blocking_reasons = self._blocking_reasons(campaign)
        campaign.warnings = self._warnings(inputs)
        campaign.last_updated_at = utc_now_iso()
        campaign.safety = SAFETY.copy()
        campaign.status = "COMPLETED" if not campaign.blocking_reasons else "BLOCKED"
        if campaign.status == "BLOCKED" and self.config.enabled and self.config.mode == "PAPER":
            campaign.status = "ACTIVE"

        self.save(campaign)
        return campaign

    def reset(self) -> None:
        self.campaign_file.write_text("{}", encoding="utf-8")

    def latest(self) -> ForwardTestCampaign | None:
        data = self._read_dict(self.campaign_file)
        return ForwardTestCampaign(**data) if data else None

    def save(self, campaign: ForwardTestCampaign) -> ForwardTestCampaign:
        self.campaign_file.write_text(json.dumps(campaign.model_dump(), indent=2, default=str), encoding="utf-8")
        return campaign

    def read_inputs(self, operator_summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "candles": self._read_list(self.data_dir / "market_candles_m1.json"),
            "contexts": self._read_list(self.data_dir / "context_snapshots.json"),
            "paper_trades": self._read_list(self.data_dir / "paper_trades.json"),
            "daemon_status": self._read_dict(self.data_dir / "daemon_status.json"),
            "operator_summary": operator_summary,
            "evidence_report": self._read_dict(self.data_dir / "evidence_gate_report.json"),
        }

    def _blocking_reasons(self, campaign: ForwardTestCampaign) -> list[str]:
        reasons: list[str] = []
        if not self.config.enabled:
            reasons.append("forward test disabled")
        if self.config.mode != "PAPER":
            reasons.append("forward test mode must be PAPER")
        if self.config.allow_broker_execution:
            reasons.append("broker execution must not be allowed")
        if campaign.days_observed < self.config.target_days:
            reasons.append("target days not reached")
        if campaign.closed_paper_trades < self.config.target_closed_paper_trades:
            reasons.append("target closed paper trades not reached")
        if campaign.recorded_candles < self.config.target_recorded_candles:
            reasons.append("target recorded candles not reached")
        if len(campaign.sessions_observed) < self.config.minimum_sessions_covered:
            reasons.append("minimum sessions not covered")
        if self.config.require_daemon_runs and campaign.daemon_loops <= 0:
            reasons.append("daemon has not run")
        if self.config.require_operator_ok and not campaign.operator_ok:
            reasons.append("operator summary not ok")
        return reasons

    def _warnings(self, inputs: dict[str, Any]) -> list[str]:
        warnings = [str(item) for item in _as_dict(inputs.get("operator_summary")).get("warnings") or []]
        evidence_status = _as_dict(inputs.get("evidence_report")).get("status")
        if evidence_status == "BLOCKED":
            warnings.append("evidence gate is blocked")
        return list(dict.fromkeys(warnings))

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
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
