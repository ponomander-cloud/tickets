from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from api.search import load_snapshot


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            snapshot = load_snapshot()
            self._json(200, {"fetched_at": snapshot["fetched_at"]})
        except Exception as exc:
            self._json(502, {"error": f"Snapshot unavailable: {type(exc).__name__}: {exc}"})

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
