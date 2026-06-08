# Trade Review / Journal Engine

Part 12 adds a deterministic journal and review layer for paper trades and strategy signals.

The journal reads:

```text
data/paper_trades.json
data/strategy_signals.json
data/context_snapshots.json
data/market_quality.json
data/paper_performance_report.json
```

It writes:

```text
data/journal_entries.json
```

This layer is journal/review only. It does not call `/commands/open-market`, does not poll `/mt5/command`, does not queue MT5 commands, and does not execute trades.

## Config

Settings live in:

```text
config/journal.yaml
```

Defaults:

```yaml
enabled: true
symbol: "XAUUSDm"
review_paper_trades: true
review_signals: true
include_context: true
include_market_quality: true
max_entries: 1000
```

## API

```text
GET  /journal/status
GET  /journal/entries
POST /journal/review-paper-trades
POST /journal/review-signals
POST /journal/generate-daily-summary
POST /journal/reset
```

## Scripts

Check journal status:

```bash
python3 scripts/check_journal.py
```

Review paper trades:

```bash
python3 scripts/review_paper_trades.py
```

Review strategy signals:

```bash
python3 scripts/review_signals.py
```

Generate daily journal summary:

```bash
python3 scripts/generate_daily_journal.py
```

Watch journal updates:

```bash
python3 scripts/watch_journal.py
```

## Classifications

Deterministic classifications:

- `VALID_WIN`
- `VALID_LOSS`
- `NO_TRADE`
- `SESSION_BLOCKED`
- `HIGH_SPREAD_BLOCKED`
- `INSUFFICIENT_DATA`
- `NO_SIGNAL`
- `OPEN_TRADE`
- `UNKNOWN`

## Mistake Flags

Deterministic mistake flags:

- `TRADED_CLOSED_SESSION`
- `HIGH_SPREAD`
- `NO_CONTEXT`
- `NO_STOP_LOSS`
- `NO_TAKE_PROFIT`
- `LOW_CONFIDENCE`
- `NONE`

## Safety

- Journal/review only.
- No live execution.
- No MT5 command queueing.
- No AI reasoning.
- No learning engine.
- Keep EA `AllowLiveTrading=false`.
