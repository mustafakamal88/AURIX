from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    load_dotenv()
    host = os.getenv("AURIX_HOST", "127.0.0.1")
    port = os.getenv("AURIX_PORT", "8765")
    url = f"http://{host}:{port}/operator/status"
    try:
        status = get_json(url)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: could not read operator status at {url}: {exc}")
        return 1

    bridge = status.get("bridge") or {}
    account = status.get("account") or {}
    market = status.get("market") or {}
    quality = market.get("quality") or {}
    context = ((status.get("context") or {}).get("latest")) or {}
    risk = status.get("risk") or {}
    paper = status.get("paper") or {}
    supervisor = status.get("supervisor") or {}
    analytics = status.get("analytics") or {}
    journal = status.get("journal") or {}
    ai_review = status.get("ai_review") or {}
    backtest = status.get("backtest") or {}
    backtest_latest = backtest.get("latest") or {}
    research = status.get("research") or {}
    research_latest = research.get("latest") or {}
    research_best_expectancy = research_latest.get("best_by_expectancy") or {}
    evidence = status.get("evidence") or {}
    evidence_latest = evidence.get("latest") or {}
    daemon = status.get("daemon") or {}
    forward_test = status.get("forward_test") or {}
    campaign = forward_test.get("campaign") or {}
    campaign_progress = campaign.get("progress") or {}
    orchestrator = status.get("orchestrator") or {}
    commands = status.get("commands") or {}
    execution = status.get("execution") or {}
    safety = status.get("safety") or {}

    print("AURIX Operator Console")
    print(f"time: {status.get('timestamp')}")
    print(f"service: {status.get('service')}")
    print(f"terminal: {bridge.get('terminal_id')}")
    print(f"snapshot: received={bridge.get('snapshot_received')} age={bridge.get('latest_snapshot_age_seconds')}")
    print(f"account: balance={account.get('balance')} equity={account.get('equity')} currency={account.get('currency')}")
    print(
        "market: "
        f"symbol={market.get('symbol')} bid={market.get('bid')} ask={market.get('ask')} "
        f"spread={market.get('spread_points')} quality_ok={quality.get('ok')}"
    )
    print(f"context: session={context.get('session_name')} regime={context.get('regime')} bias={context.get('directional_bias')}")
    print(f"risk: can_trade={risk.get('can_trade')} reasons={'; '.join(risk.get('reasons') or []) or 'none'}")
    print(f"paper: open={paper.get('open_trades')} closed={paper.get('closed_trades')}")
    print(
        "analytics: "
        f"closed={analytics.get('closed_trades')} win_rate={analytics.get('win_rate')} "
        f"total_r={analytics.get('total_r')} expectancy_r={analytics.get('expectancy_r')}"
    )
    print(f"supervisor: mode={supervisor.get('mode')} loops={supervisor.get('loop_count')} heartbeat={supervisor.get('last_heartbeat_at')}")
    print(f"journal: entries={journal.get('entries_count')} latest={journal.get('latest_classification')}")
    print(f"ai_review: reports={ai_review.get('reports_count')} actions={ai_review.get('latest_action_items_count')} summary={ai_review.get('latest_summary')}")
    print(f"backtest: trades={backtest_latest.get('trades')} expectancy_r={backtest_latest.get('expectancy_r')}")
    print(
        "research: "
        f"variants={research_latest.get('total_variants')} "
        f"best_expectancy_r={research_best_expectancy.get('expectancy_r')} "
        f"warnings={research.get('warning_count')}"
    )
    print(
        "evidence: "
        f"status={evidence_latest.get('status')} "
        f"live_ready={evidence_latest.get('live_ready')} "
        f"blocks={len(evidence_latest.get('blocking_reasons') or [])}"
    )
    print(
        "daemon: "
        f"running={daemon.get('running')} "
        f"loops={daemon.get('loop_count')} "
        f"heartbeat={daemon.get('last_heartbeat_at')} "
        f"errors={'; '.join(str(error) for error in daemon.get('errors') or []) or 'none'}"
    )
    print(
        "forward_test: "
        f"status={campaign.get('status')} "
        f"progress={campaign_progress.get('percent')} "
        f"closed_paper={campaign.get('closed_paper_trades')}"
    )
    print(
        "orchestrator: "
        f"running={orchestrator.get('running')} "
        f"session={orchestrator.get('current_session')} "
        f"allowed={orchestrator.get('session_allowed')} "
        f"forward_progress={orchestrator.get('forward_test_progress')} "
        f"evidence={orchestrator.get('evidence_status')}"
    )
    print(f"commands: open={commands.get('open_count')} total={commands.get('total_count')}")
    print(f"execution: results={execution.get('results_count')}")
    print(
        "safety: "
        f"live_trading_enabled={safety.get('live_trading_enabled')} "
        f"paper_only={safety.get('paper_only')} "
        f"ea_broker_execution_seen={safety.get('ea_broker_execution_seen')} "
        f"supervisor_queueing={safety.get('command_queueing_from_supervisor')} "
        f"strategy_command_id_present={safety.get('strategy_command_id_present')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
