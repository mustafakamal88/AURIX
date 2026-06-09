# Backtest Diagnostics and Parameter Sweep

Part 15 adds a local research layer for comparing multiple offline backtest parameter sets.

It reads recorded M1 candles from:

```text
data/market_candles_m1.json
```

It writes the latest research run to:

```text
data/research_parameter_sweep.json
```

CSV export writes:

```text
data/exports/research_parameter_sweep.csv
```

## Config

Settings live in:

```text
config/research.yaml
```

Default config:

```yaml
enabled: true
symbol: "XAUUSDm"
source_candles_file: "data/market_candles_m1.json"
stop_points_values: [200, 300, 400]
take_profit_points_values: [400, 600, 800]
lookback_range_candles_values: [5, 10, 15]
max_spread_points_values: [280, 350]
min_trades_required: 5
max_results: 100
allow_config_mutation: false
```

## API

```text
GET  /research/status
GET  /research/latest
POST /research/run-sweep
POST /research/reset
```

## Scripts

Check status:

```bash
python3 scripts/check_research.py
```

Run the parameter sweep:

```bash
python3 scripts/run_parameter_sweep.py
```

Export CSV:

```bash
python3 scripts/export_research_csv.py
```

Self-check:

```bash
PYTHONPYCACHEPREFIX=.pycache python3 scripts/self_check_research.py
```

## Selection

Each parameter combination is run through the existing offline backtest replay engine with an in-memory config.

The run records:

- best result by total R
- best result by expectancy R
- best result by profit factor
- per-variant low sample warnings when trades are below `min_trades_required`

## Safety

- Research/backtest only.
- No MT5 execution.
- No MT5 command queueing.
- No calls to `/commands/open-market`.
- No external AI calls.
- No automatic strategy config mutation.
- EA settings are not modified.
