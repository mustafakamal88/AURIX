# Safety Rules

This repository is safe by default.

- No live trading is enabled by default.
- Server commands are only queued.
- The EA blocks execution unless `AURIX_BROKER_EXECUTION=true` is manually enabled in EA inputs.
- AURIX owns risk, lot sizing, volume, spread gates, queue gates, and strategy approval.
- Do not build or enable autonomous strategy logic in Part 1.

Before any real trading, a separate Risk Governor must be built and tested. At minimum it should enforce max daily loss, max trade count, max spread, position limits, session rules, stop-loss requirements, and kill-switch behavior.
