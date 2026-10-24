"""Drives the Lambda handler like a browser: keeps cookies, sends JSON, unwraps the envelope."""
from __future__ import annotations

import json

from app import handler as h
from tests.fake_authenticator import Authenticator

HOST = "localhost:8765"


class Client:
    def __init__(self, ip: str = "10.0.0.1") -> None:
        self.cookies: dict[str, str] = {}
        self.ip = ip
        self.authenticator = Authenticator()

    def call(self, method: str, path: str, body: dict | None = None, origin: str | None = None) -> tuple[int, dict]:
        headers = {"host": HOST, "x-forwarded-proto": "http"}
        if origin is not None:
            headers["origin"] = origin
        event = {"rawPath": path, "body": json.dumps(body) if body is not None else "", "isBase64Encoded": False,
                 "headers": headers, "cookies": [f"{k}={v}" for k, v in self.cookies.items()],
                 "requestContext": {"http": {"method": method, "sourceIp": self.ip}, "requestId": "test"}}
        res = h.handler(event)
        for cookie in res.get("cookies", []):
            name, _, rest = cookie.partition("=")
            value = rest.split(";", 1)[0]
            if value:
                self.cookies[name] = value
            else:
                self.cookies.pop(name, None)
        return res["statusCode"], json.loads(res["body"])

    def get(self, path: str) -> tuple[int, dict]:
        return self.call("GET", path)

    def post(self, path: str, body: dict | None = None, **kw) -> tuple[int, dict]:
        return self.call("POST", path, body or {}, **kw)

    def sign_up(self, name: str, invite: str | None = None) -> dict:
        extra = {"invite": invite} if invite else {}
        status, opts = self.post("/api/auth/register/options", {"name": name, **extra})
        assert status == 200, opts
        credential = self.authenticator.register(opts["data"]["options"])
        status, me = self.post("/api/auth/register/verify", {"challenge_id": opts["data"]["challenge_id"],
                                                              "credential": credential, **extra})
        assert status == 200, me
        return me["data"]

    def sign_in(self) -> tuple[int, dict]:
        status, opts = self.post("/api/auth/login/options")
        assert status == 200, opts
        credential = self.authenticator.assert_(opts["data"]["options"])
        return self.post("/api/auth/login/verify", {"challenge_id": opts["data"]["challenge_id"],
                                                    "credential": credential})
