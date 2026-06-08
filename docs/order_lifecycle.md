# AURIX Order Lifecycle

Part 3 hardens command traceability from API request to EA execution result.

## Lifecycle States

```text
QUEUED
DISPATCHED
EA_RECEIVED
EXECUTION_BLOCKED
EXECUTION_FAILED
EXECUTION_FILLED
CANCELLED
EXPIRED
```

Terminal states:

```text
EXECUTION_BLOCKED
EXECUTION_FAILED
EXECUTION_FILLED
CANCELLED
EXPIRED
```

`EA_RECEIVED` is reserved for a future EA acknowledgement event. The current EA protocol reports the final execution result after polling a command.

## Command Fields

Each command stores:

- id
- type
- terminal_id
- symbol
- direction
- volume
- sl
- tp
- status
- risk_decision_id
- created_at
- dispatched_at
- completed_at
- dispatch_count
- last_error
- execution_result_id

## Dispatch Rules

- Default expiry is 30 seconds.
- Expired commands are marked `EXPIRED` and are not dispatched to the EA.
- Only `QUEUED` commands are eligible for dispatch.
- A command is dispatched once only.
- No automatic retry exists in Part 3.
- Cancelling is allowed only while a command is `QUEUED`.

## Execution Results

`POST /mt5/execution-result` accepts raw MQL5 JSON robustly and updates the matching command:

- `ok=true` with an order or deal -> `EXECUTION_FILLED`
- `ok=false` with safety gate or blocked message -> `EXECUTION_BLOCKED`
- otherwise -> `EXECUTION_FAILED`

The result is saved in `data/execution_results.json`, and the command stores the `execution_result_id`.

## Endpoints

```text
GET  /commands
GET  /commands/open
GET  /commands/{command_id}
POST /commands/{command_id}/cancel
GET  /execution/results
GET  /results
```

`GET /results` remains an alias for `GET /execution/results`.

## Scripts

Run a lifecycle check through the API:

```bash
python3 scripts/check_command_lifecycle.py
```

List open commands:

```bash
python3 scripts/list_open_commands.py
```

Cancel a queued command:

```bash
python3 scripts/cancel_command.py COMMAND_ID
```

Run local lifecycle self-checks:

```bash
python3 scripts/self_check_lifecycle.py
```

The EA live-trading gate remains unchanged. Keep `AllowLiveTrading=false` during lifecycle testing.
