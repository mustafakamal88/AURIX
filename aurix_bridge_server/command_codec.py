from __future__ import annotations

from .models import Command


def _num(value, default="0"):
    if value is None:
        return default
    return str(value)


def encode_command_for_mql5(command: Command) -> str:
    # Simple pipe-delimited command protocol for MQL5 EA.
    # Avoids needing a full JSON parser inside MQL5 for V1.
    if command.type == "OPEN_MARKET":
        return "|".join([
            "OPEN_MARKET",
            command.id,
            command.symbol or "",
            command.direction or "",
            _num(command.volume),
            _num(command.sl),
            _num(command.tp),
            command.comment.replace("|", " "),
            command.live_confirm or "",
        ])

    if command.type == "CLOSE_POSITION":
        return "|".join([
            "CLOSE_POSITION",
            command.id,
            _num(command.ticket),
            _num(command.volume),
            command.comment.replace("|", " "),
            command.live_confirm or "",
        ])

    if command.type == "CANCEL_ORDER":
        return "|".join([
            "CANCEL_ORDER",
            command.id,
            _num(command.ticket),
            command.comment.replace("|", " "),
            command.live_confirm or "",
        ])

    if command.type == "KILL_SWITCH":
        return "|".join([
            "KILL_SWITCH",
            command.id,
            command.comment.replace("|", " "),
            command.live_confirm or "",
        ])

    return "NOOP"
