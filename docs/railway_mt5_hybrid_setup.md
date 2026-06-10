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
PollSeconds=2
AllowLiveTrading=false
MaxVolume=0.01
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
6. Confirm `AllowLiveTrading=false`.
7. Confirm `MaxVolume=0.01`.

## Confirm Railway Receives Snapshots

From a local shell:

```bash
python3 scripts/check_railway_remote_health.py \
  --base-url https://your-app.up.railway.app \
  --api-key YOUR_AURIX_API_KEY
```

Or open:

```text
https://your-app.up.railway.app/dashboard?api_key=YOUR_AURIX_API_KEY
```

Confirm:

- symbol is `XAUUSDm`
- MT5 snapshot age is fresh
- runtime session id exists
- live execution is disabled
- demo execution is disabled
- command queueing is disabled

## Command Polling

The EA polls:

```text
GET /mt5/command?terminal_id=AURIX-VPS-001
```

with:

```text
X-AURIX-API-Key: YOUR_AURIX_API_KEY
```

This part does not enable command creation or queueing. A healthy response is usually:

```json
{
  "ok": true,
  "command": null,
  "status": "NO_COMMAND",
  "command_queue_enabled": false
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
- `200` from `GET /mt5/command?terminal_id=AURIX-VPS-001` with `NO_COMMAND` means command queueing is safely disabled.
- `401` or `403` means the EA `ApiKey` does not match Railway `AURIX_API_KEY`.
- `404` means the Railway deployment does not expose the expected MT5 bridge route, or the service is running old code.

After snapshots are accepted, the dashboard should show:

- symbol `XAUUSDm`
- account/feed data from MT5
- small `mt5_snapshot_age_seconds`
- live execution disabled
- demo execution disabled
- command queueing disabled

## Safety Rules

Keep:

```text
AllowLiveTrading=false
MaxVolume=0.01
```

until a later explicitly gated demo-execution part says otherwise.

Do not enable live trading. Do not enable demo broker execution. Do not queue commands. Do not create orders.
