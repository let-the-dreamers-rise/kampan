"""The storage contract: items addressed by a partition key and a sort key, like one DynamoDB table."""
from __future__ import annotations

import time
from typing import Any, Protocol

Item = dict[str, Any]


class ConditionFailed(Exception):
    """A conditional write did not apply (the item existed, or did not match)."""


class Table(Protocol):
    def get(self, pk: str, sk: str) -> Item | None: ...

    def put(self, item: Item, if_absent: bool = False) -> None: ...

    def update(self, pk: str, sk: str, values: Item, expect: Item | None = None) -> Item: ...

    def add(self, pk: str, sk: str, field: str, amount: int = 1, ttl: int | None = None) -> int: ...

    def query(self, pk: str, prefix: str = "", limit: int = 100, newest_first: bool = False) -> list[Item]: ...

    def delete(self, pk: str, sk: str) -> None: ...


def now() -> int:
    return int(time.time())


def live(item: Item | None) -> Item | None:
    """Hide items whose ttl has passed (DynamoDB deletes them lazily, so readers must check too)."""
    if item is None:
        return None
    ttl = item.get("ttl")
    return None if ttl is not None and int(ttl) < now() else item
