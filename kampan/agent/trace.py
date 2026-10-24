"""An append-only trace of tool calls, decisions and human answers, serializable to JSON lines."""
from __future__ import annotations

import dataclasses
import json
import time
from typing import Any, Callable

import numpy as np


def to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value) if f.repr}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.round(4).tolist() if value.size <= 16 else f"array{list(value.shape)}"
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else round(float(value), 5)
    if isinstance(value, np.integer):
        return int(value)
    return value


class Trace:
    """Events are appended, never edited. `events` returns a copy."""

    def __init__(self, sink: Callable[[dict], None] | None = None) -> None:
        self._events: list[dict] = []
        self._sink = sink
        self._t0 = time.perf_counter()

    def _add(self, event: dict) -> None:
        stamped = {"seq": len(self._events), "t_ms": round((time.perf_counter() - self._t0) * 1000), **event}
        self._events.append(stamped)
        if self._sink:
            self._sink(stamped)

    def tool(self, name: str, fn: Callable[..., Any], *args: Any, inputs: dict | None = None, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        self._add({"kind": "tool", "name": name, "inputs": to_jsonable(inputs or {}),
                   "output": to_jsonable(result), "ms": round((time.perf_counter() - start) * 1000, 1)})
        return result

    def capture(self, index: int, request: Any, meta: dict) -> None:
        self._add({"kind": "capture", "index": index, "request": to_jsonable(request), "meta": to_jsonable(meta)})

    def decision(self, action: Any, because: dict) -> None:
        self._add({"kind": "decision", "action": type(action).__name__, "detail": to_jsonable(action),
                   "because": to_jsonable(because)})

    def human(self, field: str, question: str, answer: Any) -> None:
        self._add({"kind": "human", "field": field, "question": question, "answer": to_jsonable(answer)})

    @property
    def events(self) -> list[dict]:
        return [dict(e) for e in self._events]

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e) for e in self._events)
