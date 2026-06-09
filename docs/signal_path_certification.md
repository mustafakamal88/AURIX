# Signal Path Certification

Part 25 adds deterministic certification for the paper signal path.

This is certification and observability only. It does not enable live trading, arm live trading, queue MT5 commands, place demo or live broker orders, modify EA settings, mutate strategy config, modify Part 23 readiness config, modify Part 24 evidence monitor config, or call external AI APIs.

## Files

```text
aurix_signal_certifier/
config/signal_certifier.yaml
data/signal_path_certification_report.json
data/signal_path_certification_history.jsonl
```

## Endpoints

```text
GET  /signal-certifier/status
GET  /signal-certifier/latest
POST /signal-certifier/certify
GET  /signal-certifier/history
POST /signal-certifier/reset
```

`POST /signal-certifier/certify` reads local data only, saves the latest report, appends history when enabled, and returns a `SignalPathCertificationReport`.

## Commands

```bash
python3 scripts/check_signal_path.py
python3 scripts/certify_signal_path.py
python3 scripts/watch_signal_path.py
python3 scripts/show_signal_path_history.py
```

## Statuses

- `NO_SIGNAL`: no signal or trade exists.
- `FAILED`: a required safety check failed or a paper trade could not be linked to its signal.
- `CERTIFIED_WITH_WARNINGS`: core paper path is valid, but observability gaps remain.
- `CERTIFIED`: all core checks passed and no warnings exist.

`CERTIFIED` does not mean live trading is allowed. It only proves paper signal path integrity.

`CERTIFIED_WITH_WARNINGS` means the trade path is valid but auditability can be improved, for example by persisting paper simulation risk decisions.

## Decision Trace

New XAUUSD Paper Strategy V1 signals store a `decision_trace` with decision-time candles and rule checks. The certifier uses that stored trace for deterministic BUY/SELL sweep-reclaim validation.

Legacy signals created before Part 25.1 may not include decision-time OHLC or rule checks. Missing legacy trace is an observability warning, not proof the strategy was wrong. The certifier must not reconstruct rule validity from latest candles; it skips V1 rule predicates with `legacy_signal_trace_missing` and can return `CERTIFIED_WITH_WARNINGS` when the rest of the path and safety checks pass.

Micro-live and demo broker execution are still not built.
