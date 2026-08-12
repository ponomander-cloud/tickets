from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import requests

SNAPSHOT_URL = "https://raw.githubusercontent.com/ponomander-cloud/tickets/main/data/latest.json"
DISPATCH_URL = "https://api.github.com/repos/ponomander-cloud/tickets/dispatches"


def load_snapshot() -> dict[str, object]:
    response = requests.get(SNAPSHOT_URL, timeout=(5.0, 15.0))
    response.raise_for_status()
    return response.json()


def request_params(path: str) -> tuple[dict[str, str], bool]:
    query = parse_qs(urlparse(path).query, keep_blank_values=True)
    params = {
        "from": query.get("from", ["Москва"])[0],
        "to": query.get("to", ["Адлер"])[0],
        "date_from": query.get("date_from", ["2026-08-15"])[0],
        "days": query.get("days", ["14"])[0],
        "top_per_day": query.get("top_per_day", ["3"])[0],
        "overall_top": query.get("overall_top", ["10"])[0],
    }
    refresh = query.get("refresh", ["false"])[0].strip().casefold() in {"1", "true", "yes"}
    return params, refresh


def snapshot_matches(snapshot: dict[str, object], params: dict[str, str]) -> bool:
    cached = snapshot["request"]
    assert isinstance(cached, dict)
    keys = ("from", "to", "date_from", "days", "top_per_day", "overall_top")
    return all(str(cached[key]) == str(params[key]) for key in keys)


def dispatch_refresh(params: dict[str, str], previous_fetched_at: str) -> None:
    token = os.environ.get("GITHUB_DISPATCH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_DISPATCH_TOKEN is not configured")
    response = requests.post(
        DISPATCH_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "event_type": "refresh-rzd",
            "client_payload": {**params, "previous_fetched_at": previous_fetched_at},
        },
        timeout=(5.0, 15.0),
    )
    response.raise_for_status()


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            params, refresh = request_params(self.path)
            snapshot = load_snapshot()
            if not snapshot_matches(snapshot, params):
                self._json(409, {"error": "No snapshot exists for this request; use refresh=true"})
                return
            if refresh:
                previous_fetched_at = str(snapshot["fetched_at"])
                dispatch_refresh(params, previous_fetched_at)
                self._json(
                    202,
                    {
                        "status": "refresh_started",
                        "previous_fetched_at": previous_fetched_at,
                    },
                )
                return
            self._json(200, snapshot)
        except requests.HTTPError as exc:
            self._json(502, {"error": f"Upstream request failed: {exc}"})
        except (ValueError, TypeError, KeyError, AssertionError) as exc:
            self._json(400, {"error": f"Invalid request or snapshot: {exc}"})
        except Exception as exc:
            self._json(500, {"error": f"Refresh failed: {type(exc).__name__}: {exc}"})

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
