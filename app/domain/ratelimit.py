"""Fixed-window rate limits per client address and route group."""
from __future__ import annotations

from app.repo.table import Table, now
from app.web import TooManyRequests

LIMITS = {"auth": 20, "measure": 30, "write": 60, "read": 300}


def check(table: Table, ip: str, group: str) -> None:
    minute = now() // 60
    count = table.add(f"RATE#{group}#{ip}", str(minute), "n", 1, ttl=now() + 180)
    if count > LIMITS[group]:
        raise TooManyRequests("too many requests from this address; wait a minute and try again")
