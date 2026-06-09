from __future__ import annotations

import os
import json
from json import JSONDecodeError
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from aurix_ai_review import AIReviewStore, AIReviewTemplateReviewer, load_ai_review_config
from aurix_analytics import PaperPerformanceStore, generate_paper_performance_report
from aurix_analytics.performance import summary_from_report
from aurix_backtest import BacktestReplayEngine, BacktestStore, load_backtest_config
from aurix_context_engine import ContextEngine, load_context_config
from aurix_journal import JournalReviewer, JournalStore, load_journal_config
from aurix_market_data import MarketDataRecorder, load_market_data_config
from aurix_operator import build_operator_summary, build_operator_status
from aurix_paper_trading import PaperLedger, PaperTradingEngine, load_paper_trading_config
from aurix_risk_governor import RiskGovernor, load_risk_config
from aurix_risk_governor.checks import as_dict, as_float, as_list
from aurix_supervisor import PaperSupervisor, load_supervisor_config
from aurix_strategy_engine import StrategyEngine, load_strategy_config
from aurix_strategy_engine.xauusd_paper_v1 import evaluate_xauusd_paper_v1, load_xauusd_paper_v1_config

from .command_codec import encode_command_for_mql5
from .models import Command, ExecutionResult, utc_now_iso
from .store import JsonStore

load_dotenv()

DATA_DIR = os.getenv("AURIX_DATA_DIR", "data")
DEFAULT_TERMINAL_ID = os.getenv("AURIX_TERMINAL_ID", "AURIX-MAC-001")

store = JsonStore(DATA_DIR)
risk_config = load_risk_config()
risk_governor = RiskGovernor(risk_config)
strategy_config = load_strategy_config()
strategy_engine = StrategyEngine(strategy_config)
xauusd_paper_v1_config = load_xauusd_paper_v1_config()
paper_config = load_paper_trading_config()
paper_ledger = PaperLedger(DATA_DIR)
paper_engine = PaperTradingEngine(paper_config, risk_config)
market_config = load_market_data_config()
market_recorder = MarketDataRecorder(DATA_DIR, market_config)
context_config = load_context_config()
context_engine = ContextEngine(DATA_DIR, context_config)
supervisor_config = load_supervisor_config()
paper_supervisor = PaperSupervisor(
    data_dir=DATA_DIR,
    config=supervisor_config,
    store=store,
    market_recorder=market_recorder,
    context_engine=context_engine,
    xauusd_paper_v1_config=xauusd_paper_v1_config,
    paper_engine=paper_engine,
    paper_ledger=paper_ledger,
    market_config=market_config,
)
performance_store = PaperPerformanceStore(DATA_DIR)
journal_config = load_journal_config()
journal_store = JournalStore(DATA_DIR, journal_config)
journal_reviewer = JournalReviewer(journal_config)
ai_review_config = load_ai_review_config()
ai_review_store = AIReviewStore(DATA_DIR, ai_review_config)
ai_review_reviewer = AIReviewTemplateReviewer(ai_review_config)
backtest_config = load_backtest_config()
backtest_store = BacktestStore(DATA_DIR, backtest_config)
backtest_engine = BacktestReplayEngine(backtest_config)

app = FastAPI(
    title="AURIX Mac/Wine MT5 Bridge",
    version="0.1.0",
    description="Mac/Wine-safe MT5 bridge using an MQL5 EA + Python API.",
)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "aurix-mac-wine-bridge",
        "name": "AURIX",
        "docs": "/docs",
        "health": "/health",
        "latest_state": "/state/latest",
        "risk_status": "/risk/status",
        "results": "/results",
        "execution_results": "/execution/results",
        "strategy_status": "/strategy/status",
        "xauusd_paper_v1": "/strategy/evaluate-paper-v1",
        "paper_status": "/paper/status",
        "market_status": "/market/status",
        "context_status": "/context/status",
        "supervisor_status": "/supervisor/status",
        "operator_status": "/operator/status",
        "paper_analytics": "/analytics/paper",
        "journal_status": "/journal/status",
        "ai_review_status": "/ai-review/status",
        "backtest_status": "/backtest/status",
    }


class OpenMarketRequest(BaseModel):
    terminal_id: str = DEFAULT_TERMINAL_ID
    symbol: str = "XAUUSDm"
    direction: str
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: str = "AURIX"
    live_confirm: Optional[str] = None


class ClosePositionRequest(BaseModel):
    terminal_id: str = DEFAULT_TERMINAL_ID
    ticket: int
    volume: Optional[float] = None
    comment: str = "AURIX-CLOSE"
    live_confirm: Optional[str] = None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


async def read_lenient_json_object(request: Request) -> dict[str, Any]:
    body = await request.body()
    text = body.decode("utf-8", errors="replace").strip().strip("\x00")

    try:
        payload, _ = json.JSONDecoder().raw_decode(text)
    except JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON snapshot payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Snapshot payload must be a JSON object.")

    return payload


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "terminal_id": str(payload.get("terminal_id") or DEFAULT_TERMINAL_ID),
        "received_at": str(payload.get("received_at") or utc_now_iso()),
        "account": _dict_or_empty(payload.get("account")),
        "tick": _dict_or_empty(payload.get("tick")),
        "candles": _list_or_empty(payload.get("candles")),
        "positions": _list_or_empty(payload.get("positions")),
        "orders": _list_or_empty(payload.get("orders")),
        "deals": _list_or_empty(payload.get("deals")),
        "raw": _dict_or_empty(payload.get("raw")),
    }


def normalize_execution_result(payload: dict[str, Any]) -> ExecutionResult:
    return ExecutionResult(
        terminal_id=str(payload.get("terminal_id") or DEFAULT_TERMINAL_ID),
        command_id=str(payload.get("command_id") or ""),
        ok=bool(payload.get("ok")),
        retcode=payload.get("retcode"),
        message=str(payload.get("message") or ""),
        order=payload.get("order"),
        deal=payload.get("deal"),
        symbol=payload.get("symbol"),
        direction=payload.get("direction"),
        volume=payload.get("volume"),
        price=payload.get("price"),
        received_at=str(payload.get("received_at") or utc_now_iso()),
        raw=_dict_or_empty(payload.get("raw")),
    )


def log_snapshot(snapshot: dict[str, Any]) -> None:
    account = _dict_or_empty(snapshot.get("account"))
    tick = _dict_or_empty(snapshot.get("tick"))
    positions = _list_or_empty(snapshot.get("positions"))
    print(
        "AURIX snapshot received "
        f"terminal_id={snapshot.get('terminal_id')} "
        f"symbol={tick.get('symbol', 'n/a')} "
        f"balance={account.get('balance', 'n/a')} "
        f"equity={account.get('equity', 'n/a')} "
        f"positions={len(positions)}",
        flush=True,
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "aurix-mac-wine-bridge",
        "terminal_id": DEFAULT_TERMINAL_ID,
    }


@app.post("/mt5/snapshot")
async def receive_snapshot(request: Request) -> dict[str, Any]:
    payload = await read_lenient_json_object(request)
    snapshot = normalize_snapshot(payload)
    store.save_snapshot(snapshot)
    market_recorder.record_snapshot(snapshot)
    log_snapshot(snapshot)
    return {"ok": True}


@app.post("/mt5/snapshot-debug")
async def receive_snapshot_debug(request: Request) -> dict[str, Any]:
    payload = await read_lenient_json_object(request)
    store.save_snapshot_debug(payload)
    return {"ok": True}


@app.post("/mt5/execution-result")
async def receive_execution_result(request: Request) -> dict[str, Any]:
    payload = await read_lenient_json_object(request)
    result = normalize_execution_result(payload)
    if not result.command_id:
        raise HTTPException(status_code=400, detail="Execution result command_id is required.")
    store.mark_result(result)
    return {"ok": True}


@app.get("/mt5/command", response_class=PlainTextResponse)
def mt5_next_command(terminal_id: str = Query(default=DEFAULT_TERMINAL_ID)) -> str:
    command = store.next_command_for_terminal(terminal_id)
    if command is None:
        return "NOOP"
    return encode_command_for_mql5(command)


@app.get("/state/latest")
def latest_state() -> dict[str, Any]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot


@app.get("/state/account")
def account_state() -> dict[str, Any]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("account", {})


@app.get("/state/positions")
def positions() -> list[dict[str, Any]]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("positions", [])


@app.get("/state/orders")
def orders() -> list[dict[str, Any]]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("orders", [])


@app.get("/state/deals")
def deals() -> list[dict[str, Any]]:
    snapshot = store.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot received yet.")
    return snapshot.get("deals", [])


@app.get("/commands")
def list_commands() -> list[dict[str, Any]]:
    return store.list_commands()


@app.get("/commands/open")
def list_open_commands() -> list[dict[str, Any]]:
    return store.list_open_commands()


@app.get("/commands/{command_id}")
def get_command(command_id: str) -> dict[str, Any]:
    command = store.get_command(command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found.")
    return command


@app.post("/commands/{command_id}/cancel")
def cancel_command(command_id: str) -> dict[str, Any]:
    ok = store.cancel_command(command_id)
    if not ok:
        command = store.get_command(command_id)
        if command is None:
            raise HTTPException(status_code=404, detail="Command not found.")
        raise HTTPException(status_code=400, detail="Only QUEUED commands can be cancelled.")
    return {"ok": True, "command_id": command_id, "status": "CANCELLED"}


@app.get("/execution/results")
def execution_results() -> list[dict[str, Any]]:
    return store.list_results()


@app.get("/results")
def list_results() -> list[dict[str, Any]]:
    return execution_results()


@app.get("/risk/status")
def risk_status() -> dict[str, Any]:
    snapshot = store.latest_snapshot()
    reasons: list[str] = []
    account: dict[str, Any] = {}
    tick: dict[str, Any] = {}
    positions: list[Any] = []
    spread_points: Optional[float] = None
    equity: Optional[float] = None
    balance: Optional[float] = None

    if snapshot is None:
        reasons.append("account snapshot missing")
        reasons.append("tick missing")
        reasons.append("spread missing")
    else:
        account = as_dict(snapshot.get("account"))
        tick = as_dict(snapshot.get("tick"))
        positions = as_list(snapshot.get("positions"))
        spread_points = as_float(tick.get("spread_points"))
        equity = as_float(account.get("equity"))
        balance = as_float(account.get("balance"))

        if not account:
            reasons.append("account snapshot missing")
        if not tick:
            reasons.append("tick missing")
        if spread_points is None:
            reasons.append("spread missing")
        elif spread_points > risk_config.max_spread_points:
            reasons.append(f"spread {spread_points} exceeds max_spread_points {risk_config.max_spread_points}")
        if len(positions) >= risk_config.max_open_positions:
            reasons.append(f"open positions {len(positions)} reached max_open_positions {risk_config.max_open_positions}")

    if not risk_config.enabled:
        reasons = []

    return {
        "enabled": risk_config.enabled,
        "latest_snapshot": {
            "terminal_id": snapshot.get("terminal_id") if snapshot else None,
            "received_at": snapshot.get("received_at") if snapshot else None,
            "symbol": tick.get("symbol") if tick else None,
            "equity": equity,
            "balance": balance,
        },
        "spread_points": spread_points,
        "open_positions": len(positions),
        "can_trade": len(reasons) == 0,
        "reasons": reasons,
        "config": risk_config.model_dump(),
    }


@app.get("/risk/decisions")
def risk_decisions() -> list[dict[str, Any]]:
    return store.list_risk_decisions()


@app.get("/strategy/status")
def strategy_status() -> dict[str, Any]:
    return strategy_engine.status(store.latest_snapshot(), store.list_strategy_signals())


@app.get("/strategy/signals")
def strategy_signals() -> list[dict[str, Any]]:
    return store.list_strategy_signals()


@app.post("/strategy/evaluate")
def evaluate_strategy() -> dict[str, Any]:
    signal = strategy_engine.evaluate(
        snapshot=store.latest_snapshot(),
        previous_signals=store.list_strategy_signals(),
    )
    store.add_strategy_signal(signal.model_dump())
    return signal.model_dump()


@app.post("/strategy/reset-signals")
def reset_strategy_signals() -> dict[str, Any]:
    store.reset_strategy_signals()
    return {"ok": True, "signals": 0}


def current_context() -> dict[str, Any]:
    latest = context_engine.latest()
    if latest is not None:
        return latest
    context = context_engine.evaluate(
        snapshot=store.latest_snapshot(),
        recorded_candles=market_recorder.list_candles(),
        market_quality=market_recorder.quality(),
    )
    context_engine.store(context)
    return context.model_dump()


def evaluate_xauusd_paper_v1_signal() -> dict[str, Any]:
    signal = evaluate_xauusd_paper_v1(
        snapshot=store.latest_snapshot(),
        context=current_context(),
        candles=market_recorder.list_candles(),
        previous_signals=store.list_strategy_signals(),
        config=xauusd_paper_v1_config,
    )
    store.add_strategy_signal(signal.model_dump())
    return signal.model_dump()


@app.post("/strategy/evaluate-paper-v1")
def strategy_evaluate_paper_v1() -> dict[str, Any]:
    return evaluate_xauusd_paper_v1_signal()


@app.get("/paper/status")
def paper_status() -> dict[str, Any]:
    return paper_engine.status(store.latest_snapshot(), paper_ledger.list_trades())


@app.get("/paper/trades")
def paper_trades() -> list[dict[str, Any]]:
    return paper_ledger.list_trades()


@app.get("/paper/open")
def paper_open_trades() -> list[dict[str, Any]]:
    return paper_ledger.list_open_trades()


@app.post("/paper/evaluate-signal")
def paper_evaluate_signal() -> dict[str, Any]:
    signal = strategy_engine.evaluate(
        snapshot=store.latest_snapshot(),
        previous_signals=store.list_strategy_signals(),
    )
    store.add_strategy_signal(signal.model_dump())
    trade, result = paper_engine.create_from_signal(
        signal=signal,
        snapshot=store.latest_snapshot(),
        open_trades=paper_ledger.list_open_trades(),
        previous_risk_decisions=store.list_risk_decisions(),
    )
    if trade is not None:
        paper_ledger.add_trade(trade)
    return result


@app.post("/paper/evaluate-paper-v1")
def paper_evaluate_paper_v1() -> dict[str, Any]:
    signal_data = evaluate_xauusd_paper_v1_signal()
    from aurix_strategy_engine.models import StrategySignal

    signal = StrategySignal(**signal_data)
    trade, result = paper_engine.create_from_signal(
        signal=signal,
        snapshot=store.latest_snapshot(),
        open_trades=paper_ledger.list_open_trades(),
        previous_risk_decisions=store.list_risk_decisions(),
    )
    if trade is not None:
        paper_ledger.add_trade(trade)
    return result


@app.post("/paper/update")
def paper_update() -> dict[str, Any]:
    trades, updated = paper_engine.update_open_trades(store.latest_snapshot(), paper_ledger.list_trades())
    paper_ledger.save_trades(trades)
    return {"ok": True, "updated": updated, "open": paper_ledger.list_open_trades()}


@app.post("/paper/close/{paper_trade_id}")
def paper_close(paper_trade_id: str) -> dict[str, Any]:
    trades = paper_ledger.list_trades()
    for trade in trades:
        if trade.get("id") == paper_trade_id:
            if trade.get("status") != "OPEN":
                raise HTTPException(status_code=400, detail="Only OPEN paper trades can be closed manually.")
            closed = paper_engine.close_manual(trade, store.latest_snapshot())
            paper_ledger.save_trades(trades)
            return {"ok": True, "paper_trade": closed}
    raise HTTPException(status_code=404, detail="Paper trade not found.")


@app.post("/paper/reset")
def paper_reset() -> dict[str, Any]:
    paper_ledger.reset()
    return {"ok": True, "trades": 0}


@app.get("/market/status")
def market_status() -> dict[str, Any]:
    return market_recorder.status()


@app.get("/market/ticks")
def market_ticks() -> list[dict[str, Any]]:
    return market_recorder.list_ticks()


@app.get("/market/candles")
def market_candles() -> list[dict[str, Any]]:
    return market_recorder.list_candles()


@app.get("/market/quality")
def market_quality() -> dict[str, Any]:
    return market_recorder.quality()


@app.post("/market/reset")
def market_reset() -> dict[str, Any]:
    market_recorder.reset()
    return {"ok": True, "ticks": 0, "candles": 0}


@app.get("/context/status")
def context_status() -> dict[str, Any]:
    return context_engine.status()


@app.get("/context/latest")
def context_latest() -> dict[str, Any]:
    latest = context_engine.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No context snapshots yet.")
    return latest


@app.get("/context/history")
def context_history() -> list[dict[str, Any]]:
    return context_engine.history()


@app.post("/context/evaluate")
def context_evaluate() -> dict[str, Any]:
    context = context_engine.evaluate(
        snapshot=store.latest_snapshot(),
        recorded_candles=market_recorder.list_candles(),
        market_quality=market_recorder.quality(),
    )
    context_engine.store(context)
    return context.model_dump()


@app.post("/context/reset")
def context_reset() -> dict[str, Any]:
    context_engine.reset()
    return {"ok": True, "contexts": 0}


@app.get("/supervisor/status")
def supervisor_status() -> dict[str, Any]:
    return paper_supervisor.status().model_dump()


@app.post("/supervisor/run-once")
def supervisor_run_once() -> dict[str, Any]:
    return paper_supervisor.run_once().model_dump()


@app.post("/supervisor/reset")
def supervisor_reset() -> dict[str, Any]:
    return paper_supervisor.reset().model_dump()


def paper_analytics_summary() -> dict[str, Any]:
    return summary_from_report(performance_store.latest())


@app.get("/analytics/paper")
def analytics_paper() -> dict[str, Any]:
    return performance_store.latest().model_dump()


@app.post("/analytics/paper/generate")
def analytics_paper_generate() -> dict[str, Any]:
    trades, signals, contexts, quality = performance_store.read_inputs()
    report = generate_paper_performance_report(trades, signals, contexts, quality)
    performance_store.save(report)
    return report.model_dump()


@app.get("/analytics/paper/summary")
def analytics_paper_summary() -> dict[str, Any]:
    return paper_analytics_summary()


@app.get("/journal/status")
def journal_status() -> dict[str, Any]:
    return journal_store.status()


@app.get("/journal/entries")
def journal_entries() -> list[dict[str, Any]]:
    return journal_store.list_entries()


@app.post("/journal/review-paper-trades")
def journal_review_paper_trades() -> dict[str, Any]:
    trades, signals, contexts, quality, _ = journal_store.read_inputs()
    entries = journal_reviewer.review_paper_trades(trades, signals, contexts, quality)
    saved = journal_store.upsert_entries(entries)
    return {"ok": True, "paper_trade_reviews": len(saved), "entries": saved}


@app.post("/journal/review-signals")
def journal_review_signals() -> dict[str, Any]:
    trades, signals, contexts, quality, _ = journal_store.read_inputs()
    entries = journal_reviewer.review_signals(signals, trades, contexts, quality)
    saved = journal_store.upsert_entries(entries)
    return {"ok": True, "signal_reviews": len(saved), "entries": saved}


@app.post("/journal/generate-daily-summary")
def journal_generate_daily_summary() -> dict[str, Any]:
    trades, signals, _, quality, analytics_report = journal_store.read_inputs()
    entry = journal_reviewer.daily_summary(trades, signals, analytics_report, quality)
    saved = journal_store.upsert_entries([entry])
    return {"ok": True, "entry": saved[0] if saved else entry.model_dump()}


@app.post("/journal/reset")
def journal_reset() -> dict[str, Any]:
    journal_store.reset()
    return {"ok": True, "entries": 0}


@app.get("/ai-review/status")
def ai_review_status() -> dict[str, Any]:
    return ai_review_store.status()


@app.get("/ai-review/reports")
def ai_review_reports() -> list[dict[str, Any]]:
    return ai_review_store.list_reports()


@app.get("/ai-review/latest")
def ai_review_latest() -> dict[str, Any]:
    latest = ai_review_store.latest()
    if latest is None:
        raise HTTPException(status_code=404, detail="No AI review reports yet.")
    return latest


@app.post("/ai-review/generate")
def ai_review_generate() -> dict[str, Any]:
    report = ai_review_reviewer.generate(ai_review_store.read_inputs())
    ai_review_store.save(report)
    return report.model_dump()


@app.post("/ai-review/reset")
def ai_review_reset() -> dict[str, Any]:
    ai_review_store.reset()
    return {"ok": True, "reports": 0}


@app.get("/backtest/status")
def backtest_status() -> dict[str, Any]:
    return backtest_store.status()


@app.get("/backtest/report")
def backtest_report() -> dict[str, Any]:
    report = backtest_store.latest_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No backtest report yet.")
    return report.model_dump()


@app.get("/backtest/trades")
def backtest_trades() -> list[dict[str, Any]]:
    return backtest_store.list_trades()


@app.post("/backtest/run")
def backtest_run() -> dict[str, Any]:
    report, trades = backtest_engine.run(backtest_store.load_candles())
    backtest_store.save(report, trades)
    return report.model_dump()


@app.post("/backtest/reset")
def backtest_reset() -> dict[str, Any]:
    backtest_store.reset()
    return {"ok": True, "trades": 0}


def operator_status_payload() -> dict[str, Any]:
    return build_operator_status(
        service="aurix-mac-wine-bridge",
        terminal_id=DEFAULT_TERMINAL_ID,
        store=store,
        market_recorder=market_recorder,
        market_config=market_config,
        context_engine=context_engine,
        risk_status=risk_status(),
        strategy_status=strategy_status(),
        paper_status=paper_status(),
        supervisor_status=supervisor_status(),
        analytics_summary=paper_analytics_summary(),
        journal_status=journal_status(),
        ai_review_status=ai_review_status(),
        backtest_status=backtest_status(),
    ).model_dump()


@app.get("/operator/status")
def operator_status() -> dict[str, Any]:
    return operator_status_payload()


@app.get("/operator/summary")
def operator_summary() -> dict[str, Any]:
    status = build_operator_status(
        service="aurix-mac-wine-bridge",
        terminal_id=DEFAULT_TERMINAL_ID,
        store=store,
        market_recorder=market_recorder,
        market_config=market_config,
        context_engine=context_engine,
        risk_status=risk_status(),
        strategy_status=strategy_status(),
        paper_status=paper_status(),
        supervisor_status=supervisor_status(),
        analytics_summary=paper_analytics_summary(),
        journal_status=journal_status(),
        ai_review_status=ai_review_status(),
        backtest_status=backtest_status(),
    )
    return build_operator_summary(status).model_dump()


@app.post("/commands/open-market")
def open_market(req: OpenMarketRequest) -> Command:
    direction = req.direction.upper()
    if direction not in {"BUY", "SELL"}:
        raise HTTPException(status_code=400, detail="direction must be BUY or SELL")

    cmd = Command(
        type="OPEN_MARKET",
        terminal_id=req.terminal_id,
        symbol=req.symbol,
        direction=direction,  # type: ignore[arg-type]
        volume=req.volume,
        sl=req.sl,
        tp=req.tp,
        comment=req.comment,
        live_confirm=req.live_confirm,
    )

    decision = risk_governor.evaluate_open_market(
        command=cmd,
        snapshot=store.latest_snapshot(),
        previous_decisions=store.list_risk_decisions(),
    )
    store.add_risk_decision(decision.model_dump())

    if not decision.approved:
        raise HTTPException(status_code=400, detail=decision.model_dump())

    cmd.risk_decision_id = decision.id
    return store.add_command(cmd)


@app.post("/commands/close-position")
def close_position(req: ClosePositionRequest) -> Command:
    cmd = Command(
        type="CLOSE_POSITION",
        terminal_id=req.terminal_id,
        ticket=req.ticket,
        volume=req.volume,
        comment=req.comment,
        live_confirm=req.live_confirm,
    )
    return store.add_command(cmd)


@app.post("/commands/kill-switch")
def kill_switch(terminal_id: str = DEFAULT_TERMINAL_ID, live_confirm: Optional[str] = None) -> Command:
    cmd = Command(
        type="KILL_SWITCH",
        terminal_id=terminal_id,
        comment="AURIX-KILL",
        live_confirm=live_confirm,
    )
    return store.add_command(cmd)


@app.post("/commands/cancel/{command_id}")
def cancel(command_id: str) -> dict[str, Any]:
    ok = store.cancel_command(command_id)
    return {"ok": ok, "command_id": command_id}
