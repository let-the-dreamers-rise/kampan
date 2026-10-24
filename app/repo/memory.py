"""In-memory table for tests and the local server. Same semantics as the DynamoDB table."""
from __future__ import annotations

import copy
import threading

from app.repo.table import ConditionFailed, Item, live


class MemoryTable:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Item] = {}
        self._lock = threading.Lock()

    def get(self, pk: str, sk: str) -> Item | None:
        with self._lock:
            return copy.deepcopy(live(self._items.get((pk, sk))))

    def put(self, item: Item, if_absent: bool = False) -> None:
        key = (item["pk"], item["sk"])
        with self._lock:
            if if_absent and live(self._items.get(key)) is not None:
                raise ConditionFailed(f"{key} exists")
            self._items[key] = copy.deepcopy(item)

    def update(self, pk: str, sk: str, values: Item, expect: Item | None = None) -> Item:
        with self._lock:
            current = live(self._items.get((pk, sk)))
            if current is None:
                raise ConditionFailed(f"{(pk, sk)} missing")
            for name, wanted in (expect or {}).items():
                if current.get(name) != wanted:
                    raise ConditionFailed(f"{name} is {current.get(name)!r}, expected {wanted!r}")
            merged = {**current, **copy.deepcopy(values)}
            self._items[(pk, sk)] = merged
            return copy.deepcopy(merged)

    def add(self, pk: str, sk: str, field: str, amount: int = 1, ttl: int | None = None) -> int:
        with self._lock:
            current = live(self._items.get((pk, sk))) or {"pk": pk, "sk": sk}
            value = int(current.get(field, 0)) + amount
            updated = {**current, field: value, **({"ttl": ttl} if ttl is not None and "ttl" not in current else {})}
            self._items[(pk, sk)] = updated
            return value

    def query(self, pk: str, prefix: str = "", limit: int = 100, newest_first: bool = False) -> list[Item]:
        with self._lock:
            rows = [copy.deepcopy(v) for (p, s), v in self._items.items()
                    if p == pk and s.startswith(prefix) and live(v) is not None]
        rows.sort(key=lambda r: r["sk"], reverse=newest_first)
        return rows[:limit]

    def delete(self, pk: str, sk: str) -> None:
        with self._lock:
            self._items.pop((pk, sk), None)
