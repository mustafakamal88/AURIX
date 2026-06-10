# Railway Cloud Bridge Setup

This guide deploys AURIX as a secure cloud bridge on Railway. Railway runs the Python/FastAPI bridge, dashboard, decision engine, runtime summary, provenance, and evidence integrity endpoints. The Windows Forex VPS runs only Exness MT5 plus `AurixBridgeEA`.

This part is deployment support only. It does not enable live trading, demo broker execution, MT5 command queueing, paper trade creation, order request creation, broker order creation, broker order modification, broker position closing, or EA trading permission changes.

## Target Architecture

```text
Railway
  AURIX FastAPI bridge/dashboard
  /dashboard
  /dashboard/runtime-summary
  /mt5/snapshot
  /mt5/command
  /healthz

Windows Forex VPS
  Exness MT5
  AurixBridgeEA
  sends HTTPS snapshots to Railway
  polls HTTPS commands from Railway
```

MT5 still needs Windows because MetaTrader and the EA run there. Railway hosts the Python bridge because it is faster to deploy, easier to update from GitHub, and can serve the dashboard from a public HTTPS URL.

## Railway Files

The deployment pack includes:

```text
railway.json
Procfile
runtime.txt
```

Railway start command:

```bash
python scripts/run_server.py
```

The runner uses:

```text
host = 0.0.0.0
port = $PORT
```

when `AURIX_RUNTIME_PROFILE=RAILWAY_CLOUD_BRIDGE`.

Local development still uses:

```text
127.0.0.1:8765
```

## Create Railway Project From GitHub

1. Push the latest AURIX code to GitHub.
2. Open Railway.
3. Create a new project.
4. Choose `Deploy from GitHub repo`.
5. Select the AURIX repository.
6. Let Railway detect Python/Nixpacks.
7. Confirm the start command is:

```bash
python scripts/run_server.py
```

## Required Variables

Set these Railway service variables:

```env
AURIX_RUNTIME_PROFILE=RAILWAY_CLOUD_BRIDGE
AURIX_HOST=0.0.0.0
AURIX_PORT=${PORT}
AURIX_PUBLIC_BASE_URL=https://your-app.up.railway.app
AURIX_REQUIRE_API_KEY_FOR_REMOTE=true
AURIX_API_KEY=replace-with-a-long-random-secret
AURIX_DASHBOARD_PASSWORD=replace-with-dashboard-password
AURIX_DASHBOARD_SESSION_SECRET=replace-with-long-random-cookie-secret
AURIX_DASHBOARD_COOKIE_NAME=aurix_dashboard_session
AURIX_DASHBOARD_SESSION_TTL_SECONDS=86400
AURIX_DASHBOARD_READ_ONLY=true
AURIX_SYMBOL=XAUUSDm
AURIX_TERMINAL_ID=AURIX-VPS-001
AURIX_BROKER_EXECUTION=false
AURIX_DATA_DIR=/data
AURIX_LOG_DIR=/data/logs
```

Use long random values for `AURIX_API_KEY` and `AURIX_DASHBOARD_SESSION_SECRET`. Do not leave them blank. In Railway cloud profile, AURIX fails closed when remote API-key auth is required but no API key is configured. `AURIX_API_KEY` is for the EA and machine/API clients. `AURIX_DASHBOARD_PASSWORD` is for human dashboard login.

## Required Volume

Mount a Railway volume at:

```text
/data
```

This lets AURIX persist snapshots, status files, event bus data, provenance counters, and evidence files across restarts.

If the volume is not mounted, Railway filesystem data may be ephemeral. The app will still run, but runtime evidence can be lost on redeploy or restart.

Current stores use `AURIX_DATA_DIR` consistently through the bridge startup. Set it to `/data` on Railway.

## API-Key Authentication

Remote profile protects sensitive endpoints with `AURIX_API_KEY`.

Accepted forms:

```text
X-AURIX-API-Key: <key>
Authorization: Bearer <key>
```

Browser dashboard requests can also authenticate with the signed HttpOnly dashboard session cookie issued by `/dashboard/login`. Do not put API keys in URLs.

Protected endpoints include:

```text
/dashboard
/dashboard/runtime-summary
/mt5/snapshot
/mt5/command
/operator/status
/operator/summary
/event-bus/status
/evidence-integrity/status
```

`/healthz` is intentionally minimal and can be used by Railway health checks.

## Open Dashboard

Railway dashboard URL pattern:

```text
https://your-app.up.railway.app/dashboard
```

Log in with `AURIX_DASHBOARD_PASSWORD`. The server verifies the password, sets a signed HttpOnly cookie, and redirects back to `/dashboard`. The dashboard JavaScript uses same-origin cookie requests and never handles the API key.

To use a custom domain, add it in Railway service settings, create the DNS record Railway provides, wait for HTTPS to become active, then open `https://your-domain/dashboard`.

If an API key was previously exposed through a dashboard URL, rotate `AURIX_API_KEY` and update the EA `ApiKey`.

The browser dashboard remains read-only and continues to poll only:

```text
GET /dashboard/runtime-summary
```

It does not call evaluation, command queueing, demo command preview/dry-run, order creation, paper trade creation, or broker execution endpoints.

## Check Remote Health

From a local machine:

```bash
python3 scripts/check_railway_remote_health.py \
  --base-url https://your-app.up.railway.app \
  --api-key YOUR_AURIX_API_KEY
```

This checks:

- `/healthz`
- `/dashboard/runtime-summary`
- `/evidence-integrity/status`

It fails if safety flags are not false.

## Configure MT5 EA On VPS

See:

```text
docs/railway_mt5_hybrid_setup.md
```

At minimum:

```text
BridgeBaseUrl=https://your-app.up.railway.app
ApiKey=YOUR_AURIX_API_KEY
TerminalId=AURIX-VPS-001
TradeSymbol=XAUUSDm
AURIX_BROKER_EXECUTION=false
MagicNumber=880001
```

In MT5 WebRequest settings, allow the Railway base URL.

## Safety Checklist

- `AURIX_REQUIRE_API_KEY_FOR_REMOTE=true`
- `AURIX_API_KEY` is set and secret
- `AURIX_BROKER_EXECUTION=false`
- Dashboard opens only with API key
- EA input `AURIX_BROKER_EXECUTION=false`
- No public firewall or proxy bypasses Railway auth
- `/dashboard/runtime-summary` shows `session_overall_safe=true`

## Rollback Or Stop Procedure

To stop Railway bridge:

1. Open the Railway project.
2. Stop the service deployment or remove the service.
3. Leave MT5 running or remove the EA from the chart.
4. Do not change `AURIX_BROKER_EXECUTION`.

To roll back code:

1. Revert to a previous GitHub commit.
2. Redeploy the Railway service.
3. Run `scripts/check_railway_remote_health.py`.

## What Remains Disabled

- Live execution.
- Broker order creation.
- Broker order modification.
- Broker position closing.
- Paper trade creation by this deployment pack.
- Order request creation by this deployment pack.
- EA trading permission changes.

## Enabling Broker Execution

Part 38.2 uses one Railway operator switch for broker execution.

Set this Railway variable intentionally:

```env
AURIX_BROKER_EXECUTION=true
```

Spread threshold, command queue behavior, strategy selection, and risk defaults are internal AURIX engine config and should not be exposed as Railway operator variables.

Required EA inputs:

```text
BridgeBaseUrl=https://web-production-bc7d4.up.railway.app
ApiKey=YOUR_AURIX_API_KEY
TerminalId=AURIX-VPS-001
TradeSymbol=XAUUSDm
AURIX_BROKER_EXECUTION=false
MagicNumber=880001
```

Broker execution remains blocked unless AURIX validates the command, including symbol, spread, SL/TP, daily risk guards, and position state.

To stop broker execution, set:

```env
AURIX_BROKER_EXECUTION=false
```

The EA can also stop execution by setting `AURIX_BROKER_EXECUTION=false`.

Never set real-money live flags for this deployment.
