from __future__ import annotations

import os
import json
from json import JSONDecodeError
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .command_codec import encode_command_for_mql5
from .models import Command, ExecutionResult, utc_now_iso
from .store import JsonStore

load_dotenv()

DATA_DIR = os.getenv("AURIX_DATA_DIR", "data")
DEFAULT_TERMINAL_ID = os.getenv("AURIX_TERMINAL_ID", "AURIX-MAC-001")

store = JsonStore(DATA_DIR)

app = FastAPI(
    title="AURIX Mac/Wine MT5 Bridge",
    version="0.1.0",
    description="Mac/Wine-safe MT5 bridge using an MQL5 EA + Python API.",
)


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
def receive_execution_result(result: ExecutionResult) -> dict[str, Any]:
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


@app.get("/results")
def list_results() -> list[dict[str, Any]]:
    return store.list_results()


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
