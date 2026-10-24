"""Sample sessions a judge can run without filming anything. Listed from samples.json next to this file."""
from __future__ import annotations

import json
from pathlib import Path

INDEX = Path(__file__).parent / "samples.json"


def list_samples() -> list[dict]:
    if not INDEX.exists():
        return []
    return json.loads(INDEX.read_text(encoding="utf-8"))
