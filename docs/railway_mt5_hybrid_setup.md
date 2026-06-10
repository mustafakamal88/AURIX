# Railway MT5 Hybrid Setup

Use this guide on the Windows Forex VPS after the AURIX bridge is deployed on Railway.

Railway runs AURIX. The Windows VPS runs only MT5 and `AurixBridgeEA`.

## EA Inputs

Set these EA inputs:

```text
BridgeBaseUrl=https://your-app.up.railway.app
ApiKey=YOUR_AURIX_API_KEY
TerminalId=AURIX-VPS-001
TradeSymbol=XAUUSDm
AURIX_BROKER_EXECUTION=false
MagicNumber=880001
```

Use your real Railway URL for `BridgeBaseUrl`. Use the same secret as Railway `AURIX_API_KEY` for `ApiKey`.

## MT5 WebRequest Allow List

In MT5:

```text
Tools -> Options -> Expert Advisors
```

Enable:

```text
Allow WebRequest for listed URL
```

Add:

```text
https://your-app.up.railway.app
```

Do not add a public HTTP URL. Use Railway HTTPS.

## Compile And Attach EA

1. Copy `mql5/Experts/AurixBridgeEA.mq5` into the MT5 data folder under `MQL5\Experts`.
2. Open MetaEditor.
3. Compile `AurixBridgeEA.mq5`.
4. Open an `XAUUSDm` chart in MT5.
5. Attach `AurixBridgeEA`.
6. Confirm EA input `AURIX_BROKER_EXECUTION=false` until broker execution is intentionally enabled.

## Confirm Railway Receives Snapshots

From a local shell:

```bash
python3 scripts/check_railway_remote_health.py \
  --base-url https://your-app.up.railway.app \
  --api-key YOUR_AURIX_API_KEY
```

Or open:

```text
https://your-app.up.railway.app/dashboard
```

Log in with the Railway `AURIX_DASHBOARD_PASSWORD`. Do not put `AURIX_API_KEY` in the browser URL. If it was previously exposed in a dashboard URL, rotate it and update the EA `ApiKey`.

Confirm:

- symbol is `XAUUSDm`
- MT5 snapshot age is fresh
- runtime session id exists
- broker execution is disabled
- AURIX queue is blocked or idle

## Command Polling

The EA polls:

```text
GET /mt5/command?terminal_id=AURIX-VPS-001
```

with:

```text
X-AURIX-API-Key: YOUR_AURIX_API_KEY
```

When broker execution is disabled, a healthy response is:

```json
{
  "ok": true,
  "command": null,
  "status": "NO_COMMAND",
  "reason": "broker execution disabled"
}
```

## Snapshot Posting

The EA posts:

```text
POST /mt5/snapshot
```

with:

```text
X-AURIX-API-Key: YOUR_AURIX_API_KEY
Content-Type: application/json
```

Snapshots contain market/account visibility only. They do not create broker orders.

A successful snapshot response looks like:

```json
{
  "ok": true,
  "status": "snapshot_received",
  "terminal_id": "AURIX-VPS-001",
  "symbol": "XAUUSDm"
}
```

## Railway Response Codes

- `200` from `POST /mt5/snapshot` means Railway accepted the EA snapshot.
- `200` from `GET /mt5/command?terminal_id=AURIX-VPS-001` with `NO_COMMAND` means no broker command is available.
- `401` or `403` means the EA `ApiKey` does not match Railway `AURIX_API_KEY`.
- `404` means the Railway deployment does not expose the expected MT5 bridge route, or the service is running old code.

After snapshots are accepted, the dashboard should show:

- symbol `XAUUSDm`
- account/feed data from MT5
- small `mt5_snapshot_age_seconds`
- broker execution disabled
- AURIX queue state shown
- spread gate shown

## Safety Rules

Keep:

```text
AURIX_BROKER_EXECUTION=false
MagicNumber=880001
```

For Part 38.2 broker execution, the only EA trading switch to enable is:

```text
AURIX_BROKER_EXECUTION=true
```

Only do this after `AURIX_BROKER_EXECUTION=true` is intentionally set in Railway.

Do not enable real-money live trading.

## Enabling Broker Execution

Railway variable:

```env
AURIX_BROKER_EXECUTION=true
```

Spread limit, command queue behavior, strategy selection, and risk defaults are internal AURIX engine config, not Railway operator variables.

EA inputs:

```text
BridgeBaseUrl=https://web-production-bc7d4.up.railway.app
ApiKey=YOUR_AURIX_API_KEY
TerminalId=AURIX-VPS-001
TradeSymbol=XAUUSDm
AURIX_BROKER_EXECUTION=false
MagicNumber=880001
```

To stop broker execution, set `AURIX_BROKER_EXECUTION=false` in Railway and in the EA.
