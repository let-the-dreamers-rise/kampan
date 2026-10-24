"""The session-signing key: from Secrets Manager on AWS, an env var locally, a random per-process key otherwise."""
from __future__ import annotations

import os
import secrets

_KEY: bytes | None = None


def session_key() -> bytes:
    global _KEY
    if _KEY is None:
        arn = os.environ.get("KAMPAN_SECRET_ARN")
        if arn:
            import boto3
            value = boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]
        else:
            value = os.environ.get("KAMPAN_SESSION_SECRET") or secrets.token_hex(32)
        if len(value) < 32:
            raise RuntimeError("session secret must be at least 32 characters")
        _KEY = value.encode("utf-8")
    return _KEY


def set_session_key(value: bytes | None) -> None:
    global _KEY
    _KEY = value
