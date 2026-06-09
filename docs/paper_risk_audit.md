# Paper Risk Audit

Part 26 persists paper-only simulated risk decisions before paper trades are written to the ledger.

This is observability only. It does not enable live trading, arm live trading, queue MT5 commands, call broker execution endpoints, place demo or live broker orders, modify EA settings, mutate strategy config, or call external AI APIs.

## Files

```text
aurix_paper_risk_audit/
config/paper_risk_audit.yaml
data/paper_risk_decisions.json
data/paper_risk_decisions_history.jsonl
```

## Endpoints

```text
GET  /paper-risk-audit/status
GET  /paper-risk-audit/latest
GET  /paper-risk-audit/history
POST /paper-risk-audit/reset
```

The endpoints are audit read/reset only. They do not create broker commands.

## Commands

```bash
python3 scripts/check_paper_risk_audit.py
python3 scripts/show_paper_risk_decisions.py
```

## Signal Path Certification

New paper trades include `risk_decision_id`, and the matching signal is updated with:

```text
paper_risk_checked=true
paper_risk_decision_id
paper_risk_status
paper_risk_checked_at
risk_check_source=PAPER_ENGINE_SIMULATION
```

The signal certifier reads `data/paper_risk_decisions.json` and validates that the decision links to the certified signal and trade.

Legacy trades before Part 26 may still lack persisted paper risk decisions. They can remain `CERTIFIED_WITH_WARNINGS` when the rest of the paper path and safety checks pass.
