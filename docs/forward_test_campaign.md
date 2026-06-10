# Forward Test Campaign Manager

Part 18 tracks paper-mode forward testing progress over multiple days and sessions.

It reads local paper evidence only:

- recorded M1 candle count
- context history sessions
- paper trade counts
- daemon loop count
- operator summary
- latest evidence gate report

It writes the latest campaign to:

```text
data/forward_test_campaign.json
```

## Config

Settings live in:

```text
config/forward_test.yaml
```

Default config:

```yaml
enabled: true
symbol: "XAUUSDm"
mode: "PAPER"
target_days: 10
target_closed_paper_trades: 50
target_recorded_candles: 1000
target_sessions: ["LONDON", "NY_PRE_MARKET", "NY_OPEN", "NY_LATE"]
minimum_sessions_covered: 3
require_daemon_runs: true
require_operator_ok: true
allow_broker_execution: false
```

## API

```text
GET  /forward-test/status
POST /forward-test/start
POST /forward-test/update
POST /forward-test/pause
POST /forward-test/reset
```

`POST /forward-test/start` creates or activates a campaign only. It does not start the daemon.

## Scripts

Check status:

```bash
python3 scripts/check_forward_test.py
```

Start:

```bash
python3 scripts/start_forward_test.py
```

Update:

```bash
python3 scripts/update_forward_test.py
```

Watch:

```bash
python3 scripts/watch_forward_test.py
```

Self-check:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 scripts/self_check_forward_test.py
```

## Safety

- Forward-test tracking only.
- Paper mode only.
- No live execution.
- No MT5 command queueing.
- No calls to `/commands/open-market`.
- No external AI calls.
- No strategy config mutation.
- EA settings are not modified.
- Campaign start does not start the daemon automatically.
