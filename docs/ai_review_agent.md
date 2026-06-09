# AI Review Agent

Part 13 adds a safe, offline-first review layer.

The current implementation is deterministic and template-based by default. It reads AURIX paper, journal, analytics, context, and market-quality data, then writes structured review reports.

Runtime reports are stored in:

```text
data/ai_review_reports.json
```

## Config

Settings live in:

```text
config/ai_review.yaml
```

Default mode:

```yaml
enabled: true
mode: "LOCAL_TEMPLATE"
allow_external_llm: false
symbol: "XAUUSDm"
include_journal: true
include_analytics: true
include_context: true
include_market_quality: true
max_journal_entries: 50
max_signals: 50
max_paper_trades: 50
```

External LLM use is disabled by default and the external adapter is intentionally not implemented for Part 13.

## API

```text
GET  /ai-review/status
GET  /ai-review/reports
GET  /ai-review/latest
POST /ai-review/generate
POST /ai-review/reset
```

## Scripts

Check status:

```bash
python3 scripts/check_ai_review.py
```

Generate a report:

```bash
python3 scripts/generate_ai_review.py
```

Watch reports:

```bash
python3 scripts/watch_ai_review.py
```

## Safety

The report safety section always includes:

- `review_only: true`
- `no_execution: true`
- `no_strategy_mutation: true`
- `external_llm_used: false`
- `commands_queued: false`

The review layer must not recommend live trading, risk increases, direct buy/sell advice, or automatic strategy changes.
