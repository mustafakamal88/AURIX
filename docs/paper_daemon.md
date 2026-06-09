# Paper Daemon / Background Runner

Part 17 adds a safe paper-only background runner inside the FastAPI server.

It can run one cycle on demand or loop in the background after an explicit start command. It does not start automatically when the server boots.

The daemon pipeline is:

1. Run the existing paper supervisor cycle.
2. Generate paper analytics on configured loop intervals.
3. Update journal entries on configured loop intervals.
4. Generate the local template AI review on configured loop intervals.
5. Evaluate the evidence gate on configured loop intervals.
6. Save daemon status and heartbeat.

It writes status to:

```text
data/daemon_status.json
```

## Config

Settings live in:

```text
config/daemon.yaml
```

Default config:

```yaml
enabled: true
mode: "PAPER"
symbol: "XAUUSDm"
interval_seconds: 5
run_context: true
run_paper_strategy: true
run_paper_update: true
run_analytics_every_loops: 12
run_journal_every_loops: 12
run_ai_review_every_loops: 60
run_evidence_every_loops: 12
allow_command_queueing: false
allow_live_execution: false
allow_external_llm: false
```

## API

```text
GET  /daemon/status
POST /daemon/run-once
POST /daemon/start
POST /daemon/stop
POST /daemon/reset
```

`POST /daemon/start` is idempotent. If the daemon is already running, it returns the current status and does not create a duplicate loop.

## Scripts

Check status:

```bash
python3 scripts/check_daemon.py
```

Run one cycle:

```bash
python3 scripts/run_daemon_once.py
```

Start:

```bash
python3 scripts/start_daemon.py
```

Stop:

```bash
python3 scripts/stop_daemon.py
```

Watch:

```bash
python3 scripts/watch_daemon.py
```

Self-check:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 scripts/self_check_daemon.py
```

## Safety

- Paper/background automation only.
- No live execution.
- No MT5 command queueing.
- No calls to `/commands/open-market`.
- No external AI calls.
- No strategy config mutation.
- EA settings are not modified.
- Daemon does not autostart on server boot.
