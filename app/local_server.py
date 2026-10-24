"""Run the Lambda handler on a laptop: python -m app.local_server --port 8765. Clips go to out/storage."""
from __future__ import annotations

import argparse
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app import handler as lambda_handler
from app.storage import MAX_UPLOAD_BYTES, LocalStorage


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, response: dict) -> None:
        body = response.get("body", "").encode("utf-8")
        self.send_response(response.get("statusCode", 200))
        for key, value in response.get("headers", {}).items():
            self.send_header(key, value)
        # Browsers dropped large close-delimited responses here; an explicit length fixes it.
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        self.close_connection = True

    def _event(self, method: str, body: str = "") -> dict:
        return {"rawPath": self.path.split("?")[0], "body": body, "isBase64Encoded": False,
                "requestContext": {"http": {"method": method}, "requestId": "local"}}

    def do_GET(self) -> None:  # noqa: N802
        self._send(lambda_handler.handler(self._event("GET")))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(min(length, lambda_handler.MAX_BODY + 1)).decode("utf-8", "replace")
        self._send(lambda_handler.handler(self._event("POST", body)))

    def do_PUT(self) -> None:  # noqa: N802
        if not self.path.startswith("/local-upload/"):
            self._send({"statusCode": 404, "body": ""})
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_UPLOAD_BYTES:
            self._send({"statusCode": 413, "body": "too large"})
            return
        store = lambda_handler.storage()
        assert isinstance(store, LocalStorage)
        store.write_bytes(self.path.removeprefix("/local-upload/"), self.rfile.read(length))
        self._send({"statusCode": 200, "body": ""})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    os.environ.setdefault("KAMPAN_LOCAL_DIR", "out/storage")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Kampan on http://127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
