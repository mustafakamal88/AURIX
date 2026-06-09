# Local Dashboard / Cockpit

Part 21 adds a read-only browser dashboard served by the local FastAPI app.

Open it at:

```text
http://127.0.0.1:8765/dashboard
```

Or run:

```bash
python3 scripts/open_dashboard.py
```

## Safety

The dashboard is monitoring only.

It displays:

```text
LIVE TRADING DISABLED
PAPER MODE ONLY
NO MT5 COMMAND QUEUEING FROM DASHBOARD
```

The dashboard does not call `/commands/open-market`, does not queue MT5 commands, does not start or stop daemon/orchestrator processes, does not mutate strategy config, and does not call external AI APIs.

## Data Sources

The dashboard reads existing GET endpoints:

```text
/operator/summary
/operator/status
/market/status
/context/latest
/paper/status
/analytics/paper/summary
/journal/status
/ai-review/latest
/evidence/latest
/forward-test/status
/orchestrator/status
/daemon/status
```

It refreshes every 5 seconds.

## Files

```text
aurix_dashboard/index.html
aurix_dashboard/styles.css
aurix_dashboard/app.js
```

No React, npm, or build step is required.
