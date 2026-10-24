"""What every API handler needs: the table, the clip storage, and an authorised caller."""
from __future__ import annotations

from dataclasses import dataclass

from app.auth import session as sessions
from app.domain import sites, users
from app.repo import table_from_env
from app.storage import Storage, storage_from_env
from app.web import Forbidden, Request

_STORAGE: Storage | None = None


def table():
    return table_from_env()


def storage() -> Storage:
    global _STORAGE
    if _STORAGE is None:
        _STORAGE = storage_from_env()
    return _STORAGE


def set_storage(store: Storage | None) -> None:
    global _STORAGE
    _STORAGE = store


@dataclass(frozen=True)
class Caller:
    user_id: str
    name: str
    site_id: str
    role: str


def caller(request: Request, role: str | None = None) -> Caller:
    """Signed-in user whose membership record still grants the session's role (and `role`, if given)."""
    s = sessions.require(request, role)
    if s.role not in sites.roles_of(table(), s.site_id, s.user_id):
        raise Forbidden("refused: your role at this site has changed; sign in again")
    user = users.get(table(), s.user_id)
    return Caller(s.user_id, user["name"], s.site_id, s.role)
