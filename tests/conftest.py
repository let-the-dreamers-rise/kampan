import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def api(tmp_path, monkeypatch):
    """A fresh in-memory table, local clip storage and session key for each API test."""
    from app.api import context
    from app.auth.secret import set_session_key
    from app.repo import set_table
    from app.repo.memory import MemoryTable
    from app.storage import LocalStorage

    monkeypatch.setenv("KAMPAN_INSECURE_COOKIES", "1")
    table = MemoryTable()
    set_table(table)
    context.set_storage(LocalStorage(tmp_path))
    set_session_key(b"k" * 48)
    yield table
    set_table(None)
    context.set_storage(None)
    set_session_key(None)
