# Session-Aware Paper Orchestrator

Part 19 adds a safe paper-only orchestrator that coordinates the daemon, context engine, forward-test campaign, evidence gate, and operator status around active sessions.

It writes status to:

```text
data/orchestrator_status.json
```

## Config

Settings live in:

```text
config/orchestrator.yaml
```

Default config:

```yaml
enabled: true
mode: "PAPER"
symbol: "XAUUSDm"
interval_seconds: 10
allowed_sessions: ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"]
run_daemon_during_allowed_sessions: true
update_forward_test_every_loops: 1
evaluate_evidence_every_loops: 6
generate_analytics_every_loops: 6
generate_journal_every_loops: 6
generate_ai_review_every_loops: 30
stop_daemon_when_session_closed: true
allow_command_queueing: false
allow_live_execution: false
allow_external_llm: false
autostart_on_server_boot: false
```

## API

```text
GET  /orchestrator/status
POST /orchestrator/run-once
POST /orchestrator/start
POST /orchestrator/stop
POST /orchestrator/reset
```

`POST /orchestrator/start` is idempotent and starts at most one background loop. The orchestrator does not start automatically on server boot.

## Scripts

Check status:

```bash
python3 scripts/check_orchestrator.py
```

Run one cycle:

```bash
python3 scripts/run_orchestrator_once.py
```

Start/stop:

```bash
python3 scripts/start_orchestrator.py
python3 scripts/stop_orchestrator.py
```

Watch:

```bash
python3 scripts/watch_orchestrator.py
```

Self-check:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 scripts/self_check_orchestrator.py
```

## Safety

- Paper orchestration only.
- No live execution.
- No MT5 command queueing.
- No calls to `/commands/open-market`.
- No external AI calls.
- No strategy config mutation.
- EA settings are not modified.
- Orchestrator does not autostart on server boot.
