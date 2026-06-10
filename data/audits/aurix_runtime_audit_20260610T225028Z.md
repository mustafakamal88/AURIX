# AURIX Runtime Audit - 2026-06-10T22:50:28Z

## Executive Summary

Audit scope covered the local AURIX working tree and persisted local runtime artifacts under `/Users/mustafakamal/AURIX`. No trading logic, strategy entry logic, risk logic, broker execution logic, MT5/EA state, Railway variables, or deployment state was changed.

Overall result: **WARN**.

The safety posture is intact: dashboard assets remain read-only/authenticated, broker execution is disabled locally, command queueing remains blocked, durable audit is required before broker command creation, and all required self-check scripts passed. The WARN status is due to stale local runtime artifacts and missing live/remote evidence, not because a broker command path was opened.

Primary findings:

- Local MT5 snapshot, strategy pipeline, decision engine, event bus, and broker reconciliation artifacts are stale in this workspace.
- Local durable audit is `DISABLED` because `DATABASE_URL` is not present locally; Railway Postgres connectivity was not verified from this machine.
- Current persisted event bus rows do not carry `runtime_session_id` at top level, and the current local event log does not contain the new strategy diagnostic event types, although the implementation and self-checks support them.
- Runtime provenance in the local dashboard summary reports `runtime_session_id=legacy_unknown` and no `deployment_commit`; this is expected for static local artifacts but weak evidence for production correlation.

No Critical Safety fixes were made. No MT5 commands were queued.

## PASS / WARN / FAIL Table

| Subsystem | Result | Evidence |
|---|---:|---|
| Runtime Snapshot / MT5 Feed | WARN | `data/latest_snapshot.json` has terminal/account/tick/candles and valid bid/ask/spread fields, but snapshot is stale. `/mt5/snapshot` only saves snapshot and runs diagnostics; it does not create broker commands. |
| Strategy Pipeline | WARN | Registry loaded with 3 registered / 3 enabled strategies and specific latest rejection `SPREAD_BLOCKED`; pipeline local latest evaluation is stale and `decision_loop_alive=false`. |
| Event Bus | WARN | Store is safe and self-check passed. Local event count is 36, but log is stale, lacks current strategy diagnostic event records, and top-level `runtime_session_id` is absent. |
| Decision Engine | PASS | Self-check passed; advisory-only safety flags remain false. Engine blocks by event bus/strategy state, broker state, spread, session, risk, low confidence, and no signal. |
| Broker Execution / Queue | PASS | `AURIX_BROKER_EXECUTION=false`; `/mt5/command` returns `NO_COMMAND` when disabled. Durable audit is prepared before command creation when gate is allowed. |
| Durable Audit / Railway Postgres | WARN | Schema and write-before-send self-check passed. Local `DATABASE_URL` missing, so local status is `DISABLED`; real Railway Postgres connectivity was not tested. |
| Trade Explanation Ledger | PASS | `data/trade_explanations/1765078137.json` exists and preserves known MT5 trade facts while leaving missing strategy/reason evidence as `unknown`. |
| Risk / Safety Gates | PASS | Broker execution status check shows internal queue `BLOCKED`, spread gate `PASS`, daily risk OK, and broker execution disabled. |
| Dashboard UI/UX | PASS | Required labels/cards are present, secret/fake-control greps returned no matches, and dashboard/auth self-checks passed. |
| Runtime Provenance | WARN | Durable audit schema supports `runtime_session_id` and `deployment_commit`; local dashboard summary currently reports `legacy_unknown` and no deployment commit. |

## Files And Artifacts Checked

Project guidance and docs:

- `AGENTS.md`
- `README.md`
- `docs/dashboard.md`
- `config/*.yaml`

Runtime artifacts:

- `data/latest_snapshot.json`
- `data/strategy_pipeline/status.json`
- `data/strategy_agents/status.json`
- `data/strategy_agents/latest_evaluations.json`
- `data/event_bus/events.jsonl`
- `data/event_bus/status.json`
- `data/event_bus/state_snapshot.json`
- `data/decision_engine/status.json`
- `data/decision_engine/report.json`
- `data/demo_broker_execution/status.json`
- `data/demo_broker_execution/commands.json`
- `data/demo_command_queue/status.json`
- `data/demo_command_queue/previews.json`
- `data/demo_command_queue/payloads.json`
- `data/demo_oms/status.json`
- `data/durable_audit/status.json`
- `data/trade_explanations/1765078137.json`
- `data/broker_reconciliation/status.json`
- `data/broker_reconciliation/report.json`

Code modules:

- `aurix_bridge_server/main.py`
- `aurix_dashboard/index.html`
- `aurix_dashboard/styles.css`
- `aurix_dashboard/app.js`
- `aurix_dashboard_runtime/summary.py`
- `aurix_decision_engine/engine.py`
- `aurix_decision_engine/models.py`
- `aurix_strategy_agents/evaluator.py`
- `aurix_strategy_agents/fast_rsi_reversal.py`
- `aurix_persistence/durable_audit.py`
- `aurix_trade_explanations/store.py`
- `aurix_demo_broker_execution/gate.py`
- `aurix_demo_broker_execution/store.py`
- `aurix_demo_command_queue/adapter.py`
- `aurix_demo_command_queue/validator.py`
- `aurix_demo_oms/oms.py`

## Exact Scripts And Commands Run

Validation scripts:

```bash
python3 scripts/self_check_dashboard.py
python3 scripts/check_dashboard_auth.py
python3 scripts/self_check_operator.py
python3 scripts/self_check_durable_audit.py
python3 scripts/self_check_trade_explanations.py
python3 scripts/self_check_decision_engine.py
python3 scripts/self_check_strategy_agents.py
python3 scripts/self_check_strategy.py
python3 scripts/self_check_xauusd_paper_v1.py
python3 scripts/self_check_xauusd_paper_v2.py
python3 scripts/self_check_event_bus.py
python3 scripts/self_check_demo_command_queue.py
python3 scripts/check_demo_broker_execution_safety.py
python3 scripts/check_demo_broker_execution_status.py
node --check aurix_dashboard/app.js
PYTHONPYCACHEPREFIX=/tmp/aurix-pycache python3 -m compileall aurix_bridge_server aurix_dashboard_runtime aurix_decision_engine aurix_strategy_agents aurix_trade_explanations aurix_persistence scripts
git diff --check
```

All commands passed. `scripts/check_dashboard_auth.py` reported that the optional Starlette TestClient redirect check was skipped because `httpx` is not installed; the script still reported `OK: dashboard auth checks passed`.

Forbidden-control and secret-leak checks:

```bash
grep -R "FORCE START\|MANUAL_OVERRIDE\|TERMINATE_ALL\|New Order\|place order\|queue command" -n aurix_dashboard aurix_dashboard_runtime aurix_bridge_server || true
grep -R "DATABASE_URL\|AURIX_API_KEY\|DASHBOARD_PASSWORD\|SESSION_SECRET" -n aurix_dashboard || true
```

Both returned no matches.

Git state inspected:

```bash
git status
git log --oneline -10
```

At audit start the tree was clean except untracked `.claude/`.

## Runtime Snapshot / MT5 Feed Audit

Result: **WARN**

Evidence:

- `data/latest_snapshot.json` exists.
- Terminal ID: `AURIX-MAC-001`.
- Account fields present: login, server, currency, company, name, balance, equity, margin fields, leverage, trade flags.
- Tick fields present and internally valid: symbol `XAUUSDm`, bid `4178.238`, ask `4178.498`, spread `260.0`, `ok=true`.
- Dashboard runtime summary reports `health=STALE` with precise reason: MT5 snapshot, event bus, and decision loop stale.

Endpoint safety:

- `/mt5/snapshot` normalizes/saves the snapshot, records market data, runs runtime diagnostics, and returns diagnostic status.
- It does not call command queue creation, broker command creation, OMS order creation, or MT5 command delivery.

Missing/stale evidence:

- Snapshot received at `2026-06-10T04:25:32.250868+00:00`, stale relative to audit time.
- Could not verify live MT5 feed freshness without touching MT5 or remote runtime.

## Strategy Pipeline Audit

Result: **WARN**

Evidence:

- `data/strategy_pipeline/status.json` exists.
- `strategy_registry_loaded=true`.
- `registered_strategy_count=3`.
- `enabled_strategy_count=3`.
- Registered names: `xauusd_paper_v1`, `xauusd_paper_v2`, `fast_rsi_first_reversal`.
- Latest Fast RSI result is specific: `BLOCKED` with `SPREAD_BLOCKED`, not generic.
- `scripts/self_check_strategy_agents.py`, `scripts/self_check_strategy.py`, `scripts/self_check_xauusd_paper_v1.py`, and `scripts/self_check_xauusd_paper_v2.py` all passed.

Missing/stale evidence:

- Local `latest_evaluation_at` is `2026-06-10T04:20:38.133443+00:00`.
- Local `decision_loop_alive=false` and `market_data_fresh=false`.
- Current local artifacts do not prove continuous live evaluation at audit time.

Implementation observations:

- `aurix_strategy_agents/evaluator.py` publishes started/completed/rejected/candidate/actionable/error diagnostic events.
- Strategy exception path returns `ERROR`, publishes `strategy_pipeline_error`, and does not queue commands.

## Event Bus Audit

Result: **WARN**

Evidence:

- `data/event_bus/status.json` exists.
- `event_count=36`, `last_sequence=36`, latest event type `DEMO_COMMAND_PREVIEW_EVENT`.
- Event bus config safety flags block live execution, command queueing, MT5 queueing, and broker order creation.
- `scripts/self_check_event_bus.py` passed.
- `scripts/self_check_strategy_agents.py` passed and validates event publication for strategy evaluation, signal events, and strategy pipeline error.

Current local event type counts:

- `STRATEGY_EVALUATION_EVENT`: 10
- `DEMO_COMMAND_PREVIEW_EVENT`: 3
- `RISK_DECISION_EVENT`: 2
- `BROKER_RECONCILIATION_EVENT`: 2
- `AUTONOMY_STATE_EVENT`: 2
- `AURIX_DECISION_EVENT`: 2
- Other state events: account, position, order, trade history, tick, candle, market quality, context, session, signal, paper trade, safety, heartbeat, order request, demo command queue.

Issues / missing evidence:

- Local event bus updated at `2026-06-10T04:20:38.220855+00:00`, stale.
- Current local `events.jsonl` rows do not include top-level `runtime_session_id`.
- Current local event log does not contain event type values `strategy_registry_loaded`, `strategy_evaluation_started`, `strategy_evaluation_completed`, `strategy_signal_rejected`, `strategy_signal_candidate`, `strategy_signal_actionable`, or `strategy_pipeline_error`. The code defines and emits these diagnostic event types, but this local persisted log does not prove them are present in current runtime data.

Safety:

- Event bus publication forcibly sets live execution, live arming, command queueing, MT5 queued, broker order created, EA modified, external LLM, and strategy mutation flags to false.
- Event bus does not create orders.

## Decision Engine Audit

Result: **PASS**

Evidence:

- `scripts/self_check_decision_engine.py` passed.
- `data/decision_engine/status.json` shows `mode=DECISION_ONLY`, `autonomy_level=ADVISORY_ONLY`, latest action `BLOCKED_BY_NO_SIGNAL`, no MT5 commands queued, and no broker order created.
- Decision engine safety model disables paper trade creation, order request creation, demo command queueing, MT5 command queueing, demo/live execution, live arming, real-account execution, EA changes, external LLM use, and strategy config mutation.

Behavior verified by code inspection:

- Missing event bus / strategy state maps to `SYSTEM_NOT_READY`.
- Broker reconciliation blockers map to `BLOCKED_BY_BROKER_STATE`.
- Spread blockers map to `BLOCKED_BY_SPREAD`.
- Session blockers map to `BLOCKED_BY_SESSION`.
- Risk blockers map to `BLOCKED_BY_RISK`.
- Low confidence maps to `BLOCKED_BY_LOW_CONFIDENCE`.
- No signal maps to `BLOCKED_BY_NO_SIGNAL`.
- Actionable BUY/SELL maps to advisory `TRADE_LONG` / `TRADE_SHORT` unless autonomy mode changes it.
- Advisory trade action does not queue commands.

Note:

- The engine does not expose every requested audit label as a direct enum name (`NO_MARKET_DATA`, `STRATEGY_EVALUATED_NO_SETUP`, etc.). It distinguishes these cases through blocking reason codes, warnings, source state, and strategy pipeline diagnostics. This is acceptable for current safety behavior but could be improved for dashboard/operator clarity.

## Broker Execution / Queue Audit

Result: **PASS**

Evidence:

- `scripts/check_demo_broker_execution_status.py` passed.
- Local status: `execution_mode=BROKER_EXECUTION_DISABLED`, `broker_execution=False`, internal queue state `BLOCKED`.
- Spread gate is `PASS` with current spread `260.0` and engine threshold `270.0`.
- Primary block: `broker execution disabled`.
- `scripts/check_demo_broker_execution_safety.py` passed.

Code path verified:

- `/mt5/command` returns `NO_COMMAND` immediately when `AURIX_BROKER_EXECUTION` is false.
- If broker execution is true and the gate allows a command, `prepare_durable_audit_for_broker_command()` must succeed before `demo_broker_execution_store.create_command()`.
- Durable audit failure returns `NO_COMMAND` with `DURABLE_AUDIT_DISABLED`, `DURABLE_AUDIT_DUPLICATE_COMMAND`, or `DURABLE_AUDIT_WRITE_FAILED`.
- Command audit is written with `queued=false` / `WRITE_BEFORE_SEND` before command creation.
- Command audit is marked `queued=true` only after queue write succeeds.
- Command comments use safe short form `AURIX-DEMO:<first8>` capped to 31 characters.
- Duplicate command protection checks durable audit `command_audit` queued status and command store pending/delivered status.

Safety:

- Dashboard JavaScript does not call command/queue write endpoints.
- Demo command queue self-check passed.

## Durable Audit / Railway Postgres Audit

Result: **WARN**

Evidence:

- `scripts/self_check_durable_audit.py` passed.
- Schema includes:
  - `aurix_events`
  - `strategy_evaluations`
  - `decision_records`
  - `trade_explanations`
  - `command_audit`
  - `broker_trade_results`
- Schema includes `runtime_session_id` and `deployment_commit` columns.
- Local dashboard summary reports durable audit `DISABLED`, database connected `false`, source of truth `local JSON cache only`.

Safety behavior:

- Missing `DATABASE_URL` blocks broker command creation through `DURABLE_AUDIT_DISABLED`.
- DB write failure blocks broker command creation through `DURABLE_AUDIT_WRITE_FAILED`.
- No broker command can be created before write-before-send durable audit completes.

Missing evidence:

- Real Railway Postgres connection/schema readiness was not tested because no local Railway credentials/URL were used or printed.
- Local `DATABASE_URL` is absent by design for this audit.

Security note:

- Dashboard grep found no `DATABASE_URL`, `AURIX_API_KEY`, dashboard password, or session secret references in dashboard assets.

## Trade Explanation Ledger Audit

Result: **PASS**

Evidence:

- `data/trade_explanations/1765078137.json` exists.
- Historical trade fields match the known MT5 report:
  - order `1765078137`
  - open deal `1633657119`
  - close deal `1633804624`
  - account `474011120 GBP demo`
  - symbol `XAUUSDm`
  - direction `SELL`
  - volume `0.01`
  - entry `4174.178`
  - SL `4192.438`
  - TP `4162.438`
  - opened `2026-06-10T09:39:08+00:00`
  - closed `2026-06-10T10:07:15+00:00`
  - result `CLOSED_TP`
  - profit `8.76 GBP`
  - comment `AURIX-DEMO`
- Strategy/reason/session/spread remain `unknown` because original evidence is missing. This is correct and not guessed.
- `scripts/self_check_trade_explanations.py` passed.

Future path:

- `prepare_durable_audit_for_broker_command()` builds a trade explanation before command queue creation and writes it to local explanation store and durable audit when DB is available.

## Risk / Safety Gates Audit

Result: **PASS**

Evidence:

- Spread threshold shown in runtime is engine/config based: `270.0`.
- Queue config/state is read from AURIX config/data files, not dashboard controls.
- Daily risk guard status is `OK`, equity loss `0.0`, drawdown `0.0`, daily risk limit `10.0%`.
- Broker order permission is `BLOCKED`; queue permission is `BLOCKED`.
- Dashboard differentiates runtime safety, trading session, broker execution switch, broker order permission, and queue permission.

Note:

- Some persisted local gate artifacts are stale; current self-checks use isolated runtime fixtures and passed.

## Dashboard UI/UX Audit

Result: **PASS**

Evidence:

- Mission Control row includes System Health, Execution Safety, Durable Audit, Strategy Pipeline, Signal State, Risk/Gates, Broker/Queue, and Next Expected.
- Durable Audit top summary uses the same `durable_audit` state as the detailed card.
- Strategy Pipeline is in Primary Operations and above lower-priority runtime infrastructure.
- Why No Trade section is immediately after Primary Operations.
- Long enum display aliases exist for action and rejection/status codes.
- Required text/labels preserved:
  - `Execution Control State`
  - `AURIX Gates`
  - `Validation / Readiness`
  - `Quick Validation`
  - `Latest Trade Explanation`
  - `Durable Audit`
  - `No trade explanation recorded yet.`
  - `BROKER EXECUTION DISABLED`
  - `EA EXECUTION DISABLED`
  - `EXECUTION STATE`
  - `READ-ONLY DASHBOARD`
  - `NO COMMANDS FROM DASHBOARD`
- Dashboard/auth self-checks passed.
- Forbidden fake-control grep returned no matches.
- Dashboard secret grep returned no matches.

No screenshots were captured in this audit.

## Runtime Provenance Audit

Result: **WARN**

Evidence:

- Durable audit store includes runtime session and deployment commit columns for all major audit tables.
- Broker command creation includes `runtime_session_id`.
- Local dashboard summary currently reports `runtime_session_id=legacy_unknown`.
- Local dashboard summary has no deployment commit.

Missing evidence:

- No live Railway runtime summary was queried.
- No fresh post-deploy record was created or inspected.
- Current local event bus rows do not include top-level runtime session correlation.

## Missing Evidence

- Fresh live MT5 snapshot at audit time.
- Fresh event bus increment during audit without invoking live runtime endpoints.
- Real Railway Postgres `DATABASE_URL` connectivity/schema readiness.
- Remote deployment commit in runtime summary.
- Fresh post-deploy durable audit row correlation.
- Browser screenshots at 1920/1440/1280.

## Stale State

- MT5 snapshot stale: `data/latest_snapshot.json` received at `2026-06-10T04:25:32.250868+00:00`.
- Strategy latest evaluation stale: `2026-06-10T04:20:38.133443+00:00`.
- Event bus stale: `2026-06-10T04:20:38.220855+00:00`.
- Decision engine stale: `2026-06-10T04:20:37.932050+00:00`.
- Broker reconciliation status is clean but stale: `2026-06-10T03:49:17.629096+00:00`.

## Dashboard Mismatches

None found in static assets/self-checks.

Known local runtime state mismatch:

- Dashboard correctly reports local Durable Audit as `DISABLED` because local `DATABASE_URL` is missing. This does not prove Railway Durable Audit is disabled.

## Event Bus Issues

- Current local events do not include `runtime_session_id` at top level.
- Current local event log lacks persisted examples of the new strategy diagnostic event types.
- Current local event bus state is stale.

## Durable Audit Issues

- Local `DATABASE_URL` missing; local durable audit status is `DISABLED`.
- Real Railway Postgres connectivity was not tested.
- Last DB write is absent locally.
- No secret leakage was found in dashboard assets.

## Safety Issues

No active safety issue found.

Broker command creation remains gated by:

- `AURIX_BROKER_EXECUTION`
- terminal allowlist
- demo account verification
- symbol allowlist
- volume limit
- session policy
- spread gate
- valid actionable signal
- confidence threshold
- SL/TP presence
- one open position rule
- daily risk guard
- duplicate pending command guard
- runtime health
- durable audit write-before-send

## Recommended Fixes

### Critical Safety

None.

### Data Loss / Audit

1. Add runtime session and deployment commit propagation to event bus records, not only durable audit rows.
   - Current local event rows have no top-level `runtime_session_id`.
   - This is audit/provenance behavior, but it touches event bus model/store plumbing and should be approved before implementation.

2. Add a Railway-only durable audit health check script that verifies schema readiness without printing `DATABASE_URL`.
   - Should report enabled/connected/schema-ready/last-write without exposing credentials.

### Runtime Correctness

1. Refresh live runtime evidence after Railway deployment and confirm:
   - MT5 snapshot fresh
   - strategy loop alive
   - event count increasing
   - decision loop fresh
   - broker reconciliation fresh

2. Make decision-engine dashboard/operator labels expose requested diagnostic categories directly where already known:
   - `NO_MARKET_DATA`
   - `STRATEGY_EVALUATION_MISSING`
   - `STRATEGY_EVALUATED_NO_SETUP`
   - `LOW_CONFIDENCE`
   - `SPREAD_BLOCKED`
   - `RISK_BLOCKED`

### Dashboard Clarity

1. Surface event bus staleness reason near Event Bus card using the same precise health reason already generated by runtime summary.
2. Surface `legacy_unknown` runtime session as a WARN badge in Runtime Provenance if no current session id exists.

### Cosmetic

1. Capture screenshots at 1920, 1440, and 1280 after starting an authenticated local/remote dashboard session.

## Manual Approval Required Before Fixing

Approval recommended before implementing:

- Event bus model/store change for `runtime_session_id` and `deployment_commit`.
- Decision-engine output taxonomy changes if they alter enum values or downstream contracts.
- Any live Railway DB verification that requires remote credentials or service access.

No approval needed for future dashboard-only copy/layout improvements that do not touch runtime or execution behavior.
