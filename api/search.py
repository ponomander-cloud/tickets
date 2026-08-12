from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from rzd_search import search

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "data" / "latest.json"
SNAPSHOT_URL = "https://raw.githubusercontent.com/ponomander-cloud/tickets/main/data/latest.json"


def verified_snapshot(params: dict[str, str]) -> dict[str, object] | None:
    try:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        response = requests.get(SNAPSHOT_URL, timeout=(5.0, 15.0))
        response.raise_for_status()
        snapshot = response.json()
    cached_request = snapshot["request"]
    comparable = ("from", "to", "date_from", "days", "top_per_day", "overall_top")
    if all(str(cached_request[key]) == str(params[key]) for key in comparable):
        snapshot["source"] = f'{snapshot["source"]} (verified live snapshot fallback)'
        return snapshot
    return None


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
            try:
                result = search(params)
            except Exception:
                result = verified_snapshot(params)
                if result is None:
                    raise
            self._json(200, result)
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
