"""Small helpers shared by the domain modules: ids, time, text validation."""
from __future__ import annotations

import math
import re
import secrets
import time
from typing import Any

from app.web import BadRequest

CONTROL = re.compile(r"[\x00-\x1f\x7f]")
ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


def new_id(nbytes: int = 8) -> str:
    return secrets.token_hex(nbytes)


def now_ms() -> int:
    return int(time.time() * 1000)


def text(value: Any, name: str, max_len: int, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise BadRequest(f"{name} must be text")
    cleaned = CONTROL.sub("", value).strip()
    if required and not cleaned:
        raise BadRequest(f"{name} is required")
    if len(cleaned) > max_len:
        raise BadRequest(f"{name} must be at most {max_len} characters")
    return cleaned


def number(value: Any, name: str, lo: float, hi: float) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise BadRequest(f"{name} must be a number") from exc
    if math.isnan(x) or not lo <= x <= hi:
        raise BadRequest(f"{name} must be between {lo:g} and {hi:g}")
    return x


def ident(value: Any, name: str) -> str:
    if not isinstance(value, str) or not ID.match(value):
        raise BadRequest(f"{name} is not a valid id")
    return value
