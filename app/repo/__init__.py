"""Data access. `Table` is the storage contract; domain modules build their records on top of it."""
from __future__ import annotations

import os

from app.repo.table import Table

_TABLE: Table | None = None


def table_from_env() -> Table:
    global _TABLE
    if _TABLE is None:
        name = os.environ.get("KAMPAN_TABLE")
        if name:
            from app.repo.dynamo import DynamoTable
            _TABLE = DynamoTable(name)
        else:
            from app.repo.memory import MemoryTable
            _TABLE = MemoryTable()
    return _TABLE


def set_table(table: Table | None) -> None:
    """Tests and the local server install their own table."""
    global _TABLE
    _TABLE = table
