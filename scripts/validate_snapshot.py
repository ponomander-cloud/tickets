from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

result = json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
fetched_at = datetime.fromisoformat(result["fetched_at"])
age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
assert age < 600, f"snapshot is not fresh: {age:.0f}s old"
assert len(result["days"]) == result["request"]["days"]
assert len(result["overall_cheapest"]) <= result["request"]["overall_top"]
assert len(result["overall_value"]) <= result["request"]["overall_top"]
for day in result["days"]:
    trains = [ticket["train_number"] for ticket in day["top_coupe"]]
    assert len(trains) == len(set(trains)), f"duplicate train on {day['date']}"
    assert len(trains) <= result["request"]["top_per_day"]
