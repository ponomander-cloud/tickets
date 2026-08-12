from __future__ import annotations

import json
import sys
from pathlib import Path

from rzd_search import search

REQUEST_PATH = Path("request.json")
OUTPUT_PATH = Path("data/latest.json")


def main() -> int:
    request_values = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    output = search(request_values)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH}: {len(output['days'])} days, "
        f"{len(output['overall_cheapest'])} cheapest offers"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
