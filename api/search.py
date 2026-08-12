from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from rzd_search import search


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            params = {
                "from": query.get("from", ["Москва"])[0],
                "to": query.get("to", ["Адлер"])[0],
                "date_from": query.get("date_from", ["2026-08-15"])[0],
                "days": query.get("days", ["14"])[0],
                "top_per_day": query.get("top_per_day", ["3"])[0],
                "overall_top": query.get("overall_top", ["10"])[0],
            }
            self._json(200, search(params))
        except (ValueError, TypeError) as exc:
            self._json(400, {"error": f"Invalid request: {exc}"})
        except Exception as exc:
            self._json(502, {"error": f"Live RZD request failed: {type(exc).__name__}: {exc}"})

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
