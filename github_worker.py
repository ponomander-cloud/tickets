from __future__ import annotations

import argparse
import json
from pathlib import Path

from rzd_search import search


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-station", required=True)
    parser.add_argument("--to-station", required=True)
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--top-per-day", type=int, required=True)
    parser.add_argument("--overall-top", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = search(
        {
            "from": args.from_station,
            "to": args.to_station,
            "date_from": args.date_from,
            "days": args.days,
            "top_per_day": args.top_per_day,
            "overall_top": args.overall_top,
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
