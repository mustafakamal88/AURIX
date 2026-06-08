# Paper Performance Analytics

Part 11 adds deterministic analytics for paper trades.

The analytics layer reads runtime JSON files:

```text
data/paper_trades.json
data/strategy_signals.json
data/context_snapshots.json
data/market_quality.json
```

It writes the latest generated report to:

```text
data/paper_performance_report.json
```

This is analytics-only. It does not call `/commands/open-market`, does not poll `/mt5/command`, does not queue commands, and does not execute trades.

## API

```text
GET  /analytics/paper
POST /analytics/paper/generate
GET  /analytics/paper/summary
```

`POST /analytics/paper/generate` reads the paper ledger, computes metrics, saves the report, and returns it.

## Scripts

Check the latest summary:

```bash
python3 scripts/check_analytics.py
```

Generate a report:

```bash
python3 scripts/generate_paper_report.py
```

Watch analytics:

```bash
python3 scripts/watch_analytics.py
```

Override watch interval:

```bash
AURIX_ANALYTICS_WATCH_SECONDS=5 python3 scripts/watch_analytics.py
```

## Metrics

The report includes:

- total, open, and closed paper trades
- wins, losses, and win rate
- total and average PnL points
- total R, average R, expectancy R
- best and worst trade R
- profit factor
- max consecutive wins and losses
- grouped performance by direction, session, and regime

If there are no closed paper trades yet, the report still succeeds and includes:

```text
no closed paper trades yet
```

## Safety

- Paper analytics only.
- No live execution.
- No MT5 command queueing.
- No AI reasoning.
- No learning engine.
- Keep EA `AllowLiveTrading=false`.
