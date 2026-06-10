# Broker Execution Cockpit

The AURIX dashboard is a read-only Broker Execution Cockpit for local and Railway bridge monitoring.

Open it at:

```text
http://127.0.0.1:8765/dashboard
```

The root URL redirects to the dashboard:

```text
http://127.0.0.1:8765/
```

Railway deployments can use:

```text
https://your-app.up.railway.app/dashboard
```

For a custom domain, opening `https://your-domain/` redirects to `https://your-domain/dashboard`. If the browser is not authenticated, `/dashboard` redirects to `/dashboard/login`.

The browser dashboard uses a server-side login session. Open `/dashboard`, log in with the Railway `AURIX_DASHBOARD_PASSWORD`, and the server sets a signed HttpOnly cookie using `AURIX_DASHBOARD_SESSION_SECRET`. The dashboard JavaScript does not read URL secrets, does not send `X-AURIX-API-Key`, and does not store secrets in browser storage.

Railway variables:

```env
AURIX_API_KEY=replace-with-ea-and-api-secret
AURIX_DASHBOARD_PASSWORD=replace-with-dashboard-password
AURIX_DASHBOARD_SESSION_SECRET=replace-with-long-random-cookie-secret
AURIX_DASHBOARD_COOKIE_NAME=aurix_dashboard_session
AURIX_DASHBOARD_SESSION_TTL_SECONDS=86400
```

`AURIX_API_KEY` is for the EA and API clients. `AURIX_DASHBOARD_PASSWORD` is for human browser login. Do not put either value in the dashboard URL. If an API key was previously opened in a dashboard URL, rotate it.

For a custom domain, add the domain in Railway service settings, configure the DNS record Railway gives you, keep HTTPS enabled, and open `https://your-domain/dashboard`.

The route index that used to appear at `/` is available at `/api` for debugging.

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

- configured `AURIX_BROKER_EXECUTION`
- EA `AURIX_BROKER_EXECUTION` from the latest snapshot raw fields
- execution state match/mismatch
- latest `/mt5/command` state, reason, and primary block
- AURIX queue state, spread gate, engine max spread, risk model, selected strategy, and latest signal status

For this XAUUSDm Exness setup, the default internal engine spread threshold is 270 points, so the cockpit should display `Engine Max Spread: 270 points`. Spread control belongs to AURIX internal engine/broker config, not Railway environment variables or MT5 EA inputs.

Runtime health is based on freshness of the bridge/runtime summary, MT5 snapshot, and event bus/runtime state. Broker execution being enabled or disabled does not make the dashboard healthy or stale by itself. Evidence/readiness files are shown as readiness warnings with expected paths when missing; they are not active trading blocks unless an explicit live execution gate requires them.

Safety Locks are permission and runtime-safety indicators, not another broker execution switch. Broker Order Permission can be `BLOCKED` with a reason such as `no actionable signal` even when the configured broker execution switch and EA input are both enabled. Legacy Gate Status is displayed as `IGNORED / RETIRED` when that legacy gate is not active runtime logic. Queue Permission includes a separate queue block reason, such as `signal gate blocked: no actionable signal`.

The header shows Runtime Safety separately from Trading Session. Runtime Safety is the read-only runtime safety assertion. Trading Session is calculated from the AURIX context session config in `config/context.yaml` using `Europe/London` timezone handling and is normalized to `ASIA`, `LONDON`, `NEW_YORK`, `OFF_SESSION`, or `UNKNOWN`.

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
