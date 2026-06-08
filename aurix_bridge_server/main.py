from __future__ import annotations

import os
import json
from json import JSONDecodeError
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from aurix_risk_governor import RiskGovernor, load_risk_config
from aurix_risk_governor.checks import as_dict, as_float, as_list

from .command_codec import encode_command_for_mql5
from .models import Command, ExecutionResult, utc_now_iso
from .store import JsonStore

load_dotenv()

DATA_DIR = os.getenv("AURIX_DATA_DIR", "data")
DEFAULT_TERMINAL_ID = os.getenv("AURIX_TERMINAL_ID", "AURIX-MAC-001")

store = JsonStore(DATA_DIR)
risk_config = load_risk_config()
risk_governor = RiskGovernor(risk_config)

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
