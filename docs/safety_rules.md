# Safety Rules

This repository is safe by default.

- No live trading is enabled by default.
- Server commands are only queued.
- The EA blocks execution unless `AllowLiveTrading=true` is manually enabled in EA inputs.
- The EA also requires each live command to include `live_confirm="I_ACCEPT_LIVE_RISK"`.
- `MaxVolume` defaults to `0.01`.
- Do not build or enable autonomous strategy logic in Part 1.

Before any real trading, a separate Risk Governor must be built and tested. At minimum it should enforce max daily loss, max trade count, max spread, position limits, session rules, stop-loss requirements, and kill-switch behavior.
