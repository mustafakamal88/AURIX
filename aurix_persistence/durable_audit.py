from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from aurix_common import deployment_commit, write_json_atomic


class DurableAuditError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    try:
        if value in {None, "unknown", ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, default=str)


def _deployment_commit() -> str | None:
    value = deployment_commit()
    return None if value == "unknown" else value


POSTGRES_SCHEMA = [
    """
    create table if not exists aurix_events (
        id uuid primary key,
        created_at timestamptz not null,
        runtime_session_id text,
        deployment_commit text,
        event_type text,
        symbol text,
        strategy_name text,
        signal_id text,
        decision_id text,
        explanation_id text,
        command_id text,
        mt5_order_id text,
        mt5_deal_id text,
        payload jsonb not null default '{}'::jsonb
    )
    """,
    """
    create table if not exists strategy_evaluations (
        id uuid primary key,
        created_at timestamptz not null,
        runtime_session_id text,
        deployment_commit text,
        symbol text,
        strategy_name text,
        status text,
        result text,
        direction_candidate text,
        confidence numeric,
        score numeric,
        rejection_reason text,
        setup_components jsonb not null default '{}'::jsonb,
        market_snapshot jsonb not null default '{}'::jsonb
    )
    """,
    """
    create table if not exists decision_records (
        id uuid primary key,
        created_at timestamptz not null,
        runtime_session_id text,
        deployment_commit text,
        symbol text,
        action text,
        strategy_name text,
        direction text,
        confidence numeric,
        score numeric,
        reason text,
        gates jsonb not null default '{}'::jsonb,
        strategy_snapshot jsonb not null default '{}'::jsonb
    )
    """,
    """
    create table if not exists trade_explanations (
        id uuid primary key,
        created_at timestamptz not null,
        runtime_session_id text,
        deployment_commit text,
        symbol text,
        direction text,
        volume numeric,
        entry numeric,
        stop_loss numeric,
        take_profit numeric,
        strategy_name text,
        strategy_family text,
        confidence numeric,
        score numeric,
        reason_summary text,
        setup_components jsonb not null default '{}'::jsonb,
        gates jsonb not null default '{}'::jsonb,
        signal_id text,
        decision_id text,
        command_id text,
        mt5_order_id text,
        mt5_position_id text,
        status text
    )
    """,
    """
    create table if not exists command_audit (
        id uuid primary key,
        created_at timestamptz not null,
        runtime_session_id text,
        deployment_commit text,
        explanation_id text,
        decision_id text,
        command_id text unique,
        command_type text,
        symbol text,
        direction text,
        volume numeric,
        entry numeric,
        stop_loss numeric,
        take_profit numeric,
        payload jsonb not null default '{}'::jsonb,
        queued boolean default false,
        queue_time timestamptz,
        status text
    )
    """,
    """
    create table if not exists broker_trade_results (
        id uuid primary key,
        created_at timestamptz not null,
        runtime_session_id text,
        deployment_commit text,
        command_id text,
        explanation_id text,
        mt5_order_id text,
        mt5_position_id text,
        open_deal_id text,
        close_deal_id text,
        symbol text,
        direction text,
        volume numeric,
        entry numeric,
        stop_loss numeric,
        take_profit numeric,
        close_price numeric,
        profit numeric,
        balance_after numeric,
        opened_at timestamptz,
        closed_at timestamptz,
        result text,
        raw_mt5 jsonb not null default '{}'::jsonb
    )
    """,
]


SQLITE_SCHEMA = [stmt.replace("uuid", "text").replace("timestamptz", "text").replace("jsonb not null default '{}'::jsonb", "text") for stmt in POSTGRES_SCHEMA]


class DurableAuditStore:
    def __init__(
        self,
        data_dir: str | Path = "data",
        *,
        database_url: str | None = None,
        runtime_session_id: str | None = None,
        deployment_commit: str | None = None,
        connect: Callable[[], Any] | None = None,
        dialect: str = "postgres",
    ):
        self.data_dir = Path(data_dir)
        self.root = self.data_dir / "durable_audit"
        self.root.mkdir(parents=True, exist_ok=True)
        self.status_file = self.root / "status.json"
        self.database_url = database_url if database_url is not None else os.getenv("DATABASE_URL")
        self.runtime_session_id = runtime_session_id
        self.deployment_commit = deployment_commit if deployment_commit is not None else _deployment_commit()
        self._connect = connect
        self.dialect = dialect
        self._status = self._initial_status()
        self._write_status()
        if self.database_url or self._connect is not None:
            try:
                self.init_schema()
            except DurableAuditError:
                pass

    @classmethod
    def sqlite_for_tests(cls, path: str | Path, data_dir: str | Path, runtime_session_id: str = "test-runtime") -> "DurableAuditStore":
        db_path = Path(path)
        return cls(
            data_dir=data_dir,
            database_url="sqlite-test",
            runtime_session_id=runtime_session_id,
            deployment_commit="test",
            connect=lambda: sqlite3.connect(db_path),
            dialect="sqlite",
        )

    @classmethod
    def sqlite_local(
        cls,
        data_dir: str | Path = "data",
        *,
        path: str | Path | None = None,
        runtime_session_id: str | None = None,
        deployment_commit: str | None = None,
    ) -> "DurableAuditStore":
        db_path = Path(path) if path is not None else Path(data_dir) / "aurix_durable_audit.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return cls(
            data_dir=data_dir,
            database_url=f"sqlite:///{db_path}",
            runtime_session_id=runtime_session_id,
            deployment_commit=deployment_commit,
            connect=lambda: sqlite3.connect(db_path),
            dialect="sqlite",
        )

    def _initial_status(self) -> dict[str, Any]:
        enabled = bool(self.database_url or self._connect is not None)
        source = "local SQLite durable audit" if self.dialect == "sqlite" and enabled else "Railway Postgres" if enabled else "local JSON cache only"
        return {
            "generated_at": utc_now_iso(),
            "durable_audit": "ENABLED" if enabled else "DISABLED",
            "database_connected": False,
            "source_of_truth": source,
            "database_url_scheme": str(self.database_url or "").split(":", 1)[0] or None,
            "last_db_write": None,
            "last_db_error": None,
            "latest_explanation_id": None,
            "latest_command_id": None,
            "latest_mt5_order_id": None,
            "latest_trade_result": None,
            "safety": {
                "durable_audit_required_for_broker_commands": True,
                "mt5_commands_queued": False,
                "broker_order_created": False,
            },
        }

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def _write_status(self) -> None:
        self._status["generated_at"] = utc_now_iso()
        write_json_atomic(self.status_file, self._status)

    def _connect_db(self) -> Any:
        if self._connect is not None:
            return self._connect()
        if not self.database_url:
            raise DurableAuditError("DATABASE_URL missing")
        try:
            import psycopg  # type: ignore

            return psycopg.connect(self.database_url)
        except ModuleNotFoundError:
            try:
                import psycopg2  # type: ignore

                return psycopg2.connect(self.database_url)
            except ModuleNotFoundError as exc:
                raise DurableAuditError("Postgres driver missing; install psycopg for Railway Postgres") from exc
        except Exception as exc:
            raise DurableAuditError(str(exc)) from exc

    def _execute(self, statements: list[tuple[str, tuple[Any, ...]]], *, write_label: str | None = None) -> None:
        if not self.database_url and self._connect is None:
            self._status.update({"durable_audit": "DISABLED", "database_connected": False, "last_db_error": "DATABASE_URL missing"})
            self._write_status()
            raise DurableAuditError("DATABASE_URL missing")
        try:
            conn = self._connect_db()
            try:
                cur = conn.cursor()
                for sql, params in statements:
                    cur.execute(sql, params)
                conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as exc:
            self._status.update({"durable_audit": "ERROR", "database_connected": False, "last_db_error": str(exc)})
            self._write_status()
            raise DurableAuditError(str(exc)) from exc
        self._status.update({"durable_audit": "ENABLED", "database_connected": True, "last_db_error": None})
        if write_label:
            self._status["last_db_write"] = f"{write_label} at {utc_now_iso()}"
        self._write_status()

    def _query_one(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        if not self.database_url and self._connect is None:
            return None
        try:
            conn = self._connect_db()
            try:
                cur = conn.cursor()
                cur.execute(sql, params)
                row = cur.fetchone()
                if row is None:
                    return None
                columns = [item[0] for item in cur.description]
                return dict(zip(columns, row))
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as exc:
            self._status.update({"durable_audit": "ERROR", "database_connected": False, "last_db_error": str(exc)})
            self._write_status()
            raise DurableAuditError(str(exc)) from exc

    def _ph(self) -> str:
        return "?" if self.dialect == "sqlite" else "%s"

    def _json_value(self, value: Any) -> Any:
        payload = value if value is not None else {}
        if self.dialect == "sqlite":
            return _json(payload)
        try:
            from psycopg.types.json import Jsonb  # type: ignore

            return Jsonb(payload)
        except Exception:
            try:
                from psycopg2.extras import Json  # type: ignore

                return Json(payload)
            except Exception:
                return _json(payload)

    def init_schema(self) -> None:
        schema = SQLITE_SCHEMA if self.dialect == "sqlite" else POSTGRES_SCHEMA
        self._execute([(stmt, ()) for stmt in schema], write_label="schema_init")

    def append_event(self, event: dict[str, Any]) -> str:
        row_id = str(event.get("id") or event.get("event_id") or uuid4())
        p = self._ph()
        self._execute(
            [
                (
                    f"insert into aurix_events (id, created_at, runtime_session_id, deployment_commit, event_type, symbol, strategy_name, signal_id, decision_id, explanation_id, command_id, mt5_order_id, mt5_deal_id, payload) values ({','.join([p]*14)})",
                    (
                        row_id,
                        event.get("created_at") or utc_now_iso(),
                        self.runtime_session_id,
                        self.deployment_commit,
                        event.get("event_type"),
                        event.get("symbol"),
                        event.get("strategy_name"),
                        event.get("signal_id"),
                        event.get("decision_id"),
                        event.get("explanation_id"),
                        event.get("command_id"),
                        event.get("mt5_order_id"),
                        event.get("mt5_deal_id"),
                        self._json_value(event.get("payload") or event),
                    ),
                )
            ],
            write_label="aurix_events",
        )
        return row_id

    def write_strategy_evaluation(self, evaluation: dict[str, Any], market_snapshot: dict[str, Any] | None = None) -> str:
        row_id = str(evaluation.get("id") or uuid4())
        p = self._ph()
        rejection = None
        rejections = _list(evaluation.get("rejection_reasons"))
        if rejections:
            first = _dict(rejections[0])
            rejection = first.get("message") or first.get("code") or str(rejections[0])
        self._execute(
            [
                (
                    f"insert into strategy_evaluations (id, created_at, runtime_session_id, deployment_commit, symbol, strategy_name, status, result, direction_candidate, confidence, score, rejection_reason, setup_components, market_snapshot) values ({','.join([p]*14)})",
                    (
                        row_id,
                        evaluation.get("generated_at") or evaluation.get("created_at") or utc_now_iso(),
                        self.runtime_session_id,
                        self.deployment_commit,
                        evaluation.get("symbol"),
                        evaluation.get("strategy_name"),
                        evaluation.get("status"),
                        evaluation.get("result") or evaluation.get("status"),
                        evaluation.get("direction"),
                        _float(evaluation.get("confidence")),
                        _float(evaluation.get("score")),
                        rejection or evaluation.get("setup_reason"),
                        self._json_value({"setup_reason": evaluation.get("setup_reason"), "decision_trace": evaluation.get("decision_trace"), "rejection_reasons": rejections}),
                        self._json_value(market_snapshot or {}),
                    ),
                )
            ],
            write_label="strategy_evaluations",
        )
        return row_id

    def write_decision_record(self, decision: dict[str, Any], *, gates: dict[str, Any] | None = None, strategy_snapshot: dict[str, Any] | None = None) -> str:
        row_id = str(decision.get("id") or decision.get("report_id") or uuid4())
        p = self._ph()
        self._execute(
            [
                (
                    f"insert into decision_records (id, created_at, runtime_session_id, deployment_commit, symbol, action, strategy_name, direction, confidence, score, reason, gates, strategy_snapshot) values ({','.join([p]*13)})",
                    (
                        row_id,
                        decision.get("generated_at") or decision.get("created_at") or utc_now_iso(),
                        self.runtime_session_id,
                        self.deployment_commit,
                        decision.get("symbol"),
                        decision.get("action"),
                        decision.get("strategy") or decision.get("strategy_name"),
                        decision.get("direction"),
                        _float(decision.get("confidence")),
                        _float(decision.get("score")),
                        decision.get("setup_reason") or decision.get("top_blocking_reason") or decision.get("reason"),
                        self._json_value(gates or {}),
                        self._json_value(strategy_snapshot or {}),
                    ),
                )
            ],
            write_label="decision_records",
        )
        return row_id

    def write_trade_explanation(self, explanation: dict[str, Any], *, explanation_id: str | None = None, command_id: str | None = None, decision_id: str | None = None) -> str:
        row_id = str(explanation_id or explanation.get("id") or uuid4())
        p = self._ph()
        evidence = _dict(explanation.get("evidence"))
        if self.dialect == "sqlite":
            sql = f"insert into trade_explanations (id, created_at, runtime_session_id, deployment_commit, symbol, direction, volume, entry, stop_loss, take_profit, strategy_name, strategy_family, confidence, score, reason_summary, setup_components, gates, signal_id, decision_id, command_id, mt5_order_id, mt5_position_id, status) values ({','.join([p]*23)}) on conflict(id) do update set command_id=excluded.command_id, mt5_order_id=excluded.mt5_order_id, status=excluded.status, gates=excluded.gates"
        else:
            sql = f"insert into trade_explanations (id, created_at, runtime_session_id, deployment_commit, symbol, direction, volume, entry, stop_loss, take_profit, strategy_name, strategy_family, confidence, score, reason_summary, setup_components, gates, signal_id, decision_id, command_id, mt5_order_id, mt5_position_id, status) values ({','.join([p]*23)}) on conflict (id) do update set command_id=excluded.command_id, mt5_order_id=excluded.mt5_order_id, status=excluded.status, gates=excluded.gates"
        self._execute(
            [
                (
                    sql,
                    (
                        row_id,
                        explanation.get("created_at") or utc_now_iso(),
                        self.runtime_session_id,
                        self.deployment_commit,
                        explanation.get("symbol"),
                        explanation.get("direction"),
                        _float(explanation.get("volume")),
                        _float(explanation.get("entry")),
                        _float(explanation.get("stop_loss")),
                        _float(explanation.get("take_profit")),
                        explanation.get("strategy_name"),
                        explanation.get("strategy_family"),
                        _float(explanation.get("confidence")),
                        _float(explanation.get("score")),
                        explanation.get("reason_summary"),
                        self._json_value(explanation.get("setup_components") or {}),
                        self._json_value(evidence.get("spread_risk_broker_gates") or {}),
                        evidence.get("source_signal_id") or explanation.get("signal_id"),
                        decision_id or evidence.get("decision_id"),
                        command_id or evidence.get("command_payload_id"),
                        explanation.get("mt5_order_id"),
                        explanation.get("mt5_position_id"),
                        explanation.get("result") or explanation.get("status"),
                    ),
                )
            ],
            write_label="trade_explanations",
        )
        self._status["latest_explanation_id"] = row_id
        self._status["latest_mt5_order_id"] = explanation.get("mt5_order_id")
        self._status["latest_trade_result"] = explanation.get("result") or explanation.get("status")
        self._write_status()
        return row_id

    def write_command_audit(self, command: dict[str, Any], *, explanation_id: str | None = None, decision_id: str | None = None, queued: bool = False, status: str = "PENDING_AUDIT") -> str:
        command_id = str(command.get("command_id") or uuid4().hex)
        row_id = str(command.get("audit_id") or uuid4())
        p = self._ph()
        if self.dialect == "sqlite":
            sql = f"insert into command_audit (id, created_at, runtime_session_id, deployment_commit, explanation_id, decision_id, command_id, command_type, symbol, direction, volume, entry, stop_loss, take_profit, payload, queued, queue_time, status) values ({','.join([p]*18)}) on conflict(command_id) do update set payload=excluded.payload, queued=excluded.queued, queue_time=excluded.queue_time, status=excluded.status"
        else:
            sql = f"insert into command_audit (id, created_at, runtime_session_id, deployment_commit, explanation_id, decision_id, command_id, command_type, symbol, direction, volume, entry, stop_loss, take_profit, payload, queued, queue_time, status) values ({','.join([p]*18)}) on conflict (command_id) do update set payload=excluded.payload, queued=excluded.queued, queue_time=excluded.queue_time, status=excluded.status"
        self._execute(
            [
                (
                    sql,
                    (
                        row_id,
                        command.get("created_at") or utc_now_iso(),
                        self.runtime_session_id,
                        self.deployment_commit,
                        explanation_id,
                        decision_id,
                        command_id,
                        command.get("action") or command.get("command_type"),
                        command.get("symbol"),
                        command.get("side") or command.get("direction"),
                        _float(command.get("volume")),
                        _float(command.get("entry")),
                        _float(command.get("stop_loss")),
                        _float(command.get("take_profit")),
                        self._json_value(command),
                        bool(queued),
                        command.get("queued_at") if queued else None,
                        status,
                    ),
                )
            ],
            write_label="command_audit",
        )
        self._status["latest_command_id"] = command_id
        self._write_status()
        return command_id

    def command_already_queued(self, command_id: str) -> bool:
        p = self._ph()
        row = self._query_one(f"select command_id, queued, status from command_audit where command_id={p}", (command_id,))
        return bool(row and row.get("queued") in {True, 1, "1", "t", "true", "True"})

    def mark_duplicate_command_blocked(self, command_id: str) -> None:
        p = self._ph()
        self._execute([(f"update command_audit set status={p} where command_id={p}", ("DUPLICATE_BLOCKED", command_id))], write_label="command_audit_duplicate_blocked")

    def mark_command_queued(self, command_id: str, command: dict[str, Any] | None = None) -> None:
        p = self._ph()
        self._execute(
            [(f"update command_audit set queued={p}, queue_time={p}, status={p}, payload={p} where command_id={p}", (True, utc_now_iso(), "QUEUED", self._json_value(command or {}), command_id))],
            write_label="command_audit_queued",
        )
        self._status["latest_command_id"] = command_id
        self._write_status()

    def write_broker_execution_result(self, result: dict[str, Any]) -> str:
        row_id = str(result.get("id") or uuid4())
        p = self._ph()
        self._execute(
            [
                (
                    f"insert into broker_trade_results (id, created_at, runtime_session_id, deployment_commit, command_id, explanation_id, mt5_order_id, mt5_position_id, open_deal_id, close_deal_id, symbol, direction, volume, entry, stop_loss, take_profit, close_price, profit, balance_after, opened_at, closed_at, result, raw_mt5) values ({','.join([p]*23)})",
                    (
                        row_id,
                        result.get("received_at") or result.get("created_at") or utc_now_iso(),
                        self.runtime_session_id,
                        self.deployment_commit,
                        result.get("command_id"),
                        result.get("explanation_id"),
                        str(result.get("order") or result.get("mt5_order_id") or "") or None,
                        str(result.get("position") or result.get("mt5_position_id") or "") or None,
                        str(result.get("deal") or result.get("open_deal_id") or "") or None,
                        str(result.get("close_deal_id") or "") or None,
                        result.get("symbol"),
                        result.get("side") or result.get("direction"),
                        _float(result.get("volume")),
                        _float(result.get("price") or result.get("entry")),
                        _float(result.get("stop_loss") or result.get("sl")),
                        _float(result.get("take_profit") or result.get("tp")),
                        _float(result.get("close_price")),
                        _float(result.get("profit")),
                        _float(result.get("balance_after")),
                        result.get("opened_at"),
                        result.get("closed_at"),
                        result.get("status") or result.get("result"),
                        self._json_value(result),
                    ),
                )
            ],
            write_label="broker_trade_results",
        )
        self._status["latest_mt5_order_id"] = str(result.get("order") or result.get("mt5_order_id") or "") or self._status.get("latest_mt5_order_id")
        self._status["latest_trade_result"] = result.get("status") or result.get("result")
        self._write_status()
        return row_id
