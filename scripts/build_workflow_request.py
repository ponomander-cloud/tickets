from __future__ import annotations

import json
import os
from pathlib import Path


def value(name: str, default: str) -> str:
    event = os.environ["EVENT_NAME"]
    if event == "repository_dispatch":
        return os.environ.get(f"PAYLOAD_{name}") or default
    if event == "workflow_dispatch":
        return os.environ.get(f"INPUT_{name}") or default
    return default


request = {
    "from": value("FROM", "Москва"),
    "to": value("TO", "Адлер"),
    "date_from": value("DATE_FROM", "2026-08-15"),
    "days": int(value("DAYS", "14")),
    "top_per_day": int(value("TOP_PER_DAY", "3")),
    "overall_top": int(value("OVERALL_TOP", "10")),
    "same_coupe": int(value("SAME_COUPE", "0")),
}
Path("request.json").write_text(
    json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
