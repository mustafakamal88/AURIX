# Evidence Gate / Live Readiness Guard

Part 16 adds a deterministic readiness gate for reviewing whether the system has enough evidence to be considered beyond research mode.

It reads local reports and runtime summaries only:

- paper performance report
- backtest report
- research parameter sweep report
- market candle count and market quality
- operator status and summary
- journal entries
- latest local AI review report, when available

It writes the latest report to:

```text
data/evidence_gate_report.json
```

## Config

Settings live in:

```text
config/evidence_gate.yaml
```

Default config:

```yaml
enabled: true
symbol: "XAUUSDm"
minimum_closed_paper_trades: 50
minimum_backtest_trades: 50
minimum_recorded_candles: 1000
minimum_profitable_sessions: 3
minimum_expectancy_r: 0.10
minimum_profit_factor: 1.20
maximum_consecutive_losses: 5
minimum_days_forward_tested: 10
require_operator_ok: true
require_market_quality_ok: true
require_no_open_commands: true
require_live_trading_disabled: true
allow_live_readiness: false
```

## API

```text
GET  /evidence/status
GET  /evidence/latest
POST /evidence/evaluate
POST /evidence/reset
```

## Scripts

Check status:

```bash
python3 scripts/check_evidence.py
```

Evaluate:

```bash
python3 scripts/evaluate_evidence_gate.py
```

Watch:

```bash
python3 scripts/watch_evidence.py
```

Self-check:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 scripts/self_check_evidence_gate.py
```

## Statuses

- `BLOCKED`: evidence is missing or one or more hard checks fail.
- `WATCHLIST`: most checks pass, but at least one blocking reason remains.
- `ELIGIBLE_PAPER_ONLY`: all deterministic checks pass, but live readiness is still disabled by config.

Because `allow_live_readiness: false`, `live_ready` must remain `false`.

## Safety

- Evaluation only.
- No MT5 execution.
- No MT5 command queueing.
- No calls to `/commands/open-market`.
- No external AI calls.
- No automatic config mutation.
- EA settings are not modified.
