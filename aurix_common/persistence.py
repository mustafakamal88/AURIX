from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _target_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _temp_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}")


def write_text_atomic(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = _target_lock(target)
    tmp = _temp_path(target)
    with lock:
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass


def write_json_atomic(path: str | Path, value: Any, *, indent: int | None = 2) -> None:
    write_text_atomic(path, json.dumps(value, indent=indent, default=str))
