# AURIX Mac/Wine MT5 Bridge Architecture

The bridge exists because macOS Python cannot reliably call a Wine-hosted MT5 terminal through the official `MetaTrader5` Python package.

```text
macOS Python/FastAPI
  - receives MT5 snapshots
  - stores latest account/market/position/order/deal state
  - queues commands
  - records execution results

MQL5 EA inside MT5/Wine
  - sends snapshots to FastAPI with WebRequest
  - polls for one queued command at a time
  - blocks execution by default
  - reports execution results back to FastAPI

Exness MT5 account
  - connected only through MT5 and the attached EA
```

The server stores local JSON state under `data/`:

- `latest_snapshot.json`
- `commands.json`
- `execution_results.json`

The EA command protocol is intentionally simple pipe-delimited text for Part 1, so MQL5 does not need a JSON parser for polling commands.
