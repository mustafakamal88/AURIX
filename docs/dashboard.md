# Broker Execution Cockpit

The AURIX dashboard is a read-only Broker Execution Cockpit for local and Railway bridge monitoring.

Open it at:

```text
http://127.0.0.1:8765/dashboard
```

Railway deployments can use:

```text
https://your-app.up.railway.app/dashboard?api_key=YOUR_AURIX_API_KEY
```

The dashboard JavaScript reads `api_key` from the current URL query and sends it as an `X-AURIX-API-Key` header. The key is not hardcoded, not displayed, and not stored in localStorage.

## Read-Only Safety

The dashboard does not trade. It does not call `/commands/open-market`, does not queue MT5 commands, does not start or stop daemon/orchestrator processes, does not mutate strategy config, does not change EA settings, and does not call external AI APIs.

Visible safety indicators include:

```text
BROKER EXECUTION ENABLED/DISABLED
EA EXECUTION ENABLED/DISABLED
EXECUTION STATE MATCHED/MISMATCH
READ-ONLY DASHBOARD
NO COMMANDS FROM DASHBOARD
```

## Broker Execution Display

The cockpit compares:

- Railway `AURIX_BROKER_EXECUTION`
- EA `AURIX_BROKER_EXECUTION` from the latest snapshot raw fields
- execution state match/mismatch
- latest `/mt5/command` state, reason, and primary block
- AURIX queue state, spread gate, engine max spread, risk model, selected strategy, and latest signal status

For this XAUUSDm Exness setup, the default internal engine spread threshold is 270 points, so the cockpit should display `Engine Max Spread: 270 points`. Spread control belongs to AURIX internal engine/broker config, not Railway environment variables or MT5 EA inputs.

MT5 account login determines whether the account is demo or live. The dashboard does not expose separate demo/live execution controls.

## Sections

- Execution Control State
- AURIX Gates
- Validation / Readiness
- Account / Market
- Strategy / Paper / Research
- Forward Test / Long Run
- Warnings / Blocks

The dashboard refreshes every 4 seconds and uses read-only runtime summary data.
