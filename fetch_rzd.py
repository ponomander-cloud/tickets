from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rzd_api import RzdClient

REQUEST_PATH = Path("request.json")
OUTPUT_PATH = Path("data/latest.json")


def load_request() -> dict[str, Any]:
    req = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    origin = str(req.get("from", "")).strip()
    destination = str(req.get("to", "")).strip()
    start = date.fromisoformat(str(req.get("date_from", "")))
    days = int(req.get("days", 14))
    top_per_day = int(req.get("top_per_day", 3))
    overall_top = int(req.get("overall_top", 10))
    if not origin or not destination:
        raise ValueError("'from' and 'to' are required")
    if not 1 <= days <= 31:
        raise ValueError("'days' must be between 1 and 31")
    if not 1 <= top_per_day <= 10:
        raise ValueError("'top_per_day' must be between 1 and 10")
    if not 1 <= overall_top <= 50:
        raise ValueError("'overall_top' must be between 1 and 50")
    return {
        "from": origin,
        "to": destination,
        "date_from": start,
        "days": days,
        "top_per_day": top_per_day,
        "overall_top": overall_top,
    }


def is_coupe(car_type: str | None) -> bool:
    if not car_type:
        return False
    value = car_type.strip().casefold()
    return value in {
        "compartment",
        "купе",
        "coupe",
        "kupe",
    }


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def duration_info(departure: str | None, arrival: str | None) -> tuple[int | None, str | None]:
    dep = parse_dt(departure)
    arr = parse_dt(arrival)
    if dep is None or arr is None:
        return None, None
    # RZD normally returns full date-times. If offsets are absent, both are still local route datetimes.
    delta = arr - dep
    minutes = int(delta.total_seconds() // 60)
    if minutes < 0:
        return None, None
    hours, mins = divmod(minutes, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        label = f"{days} д {hours} ч {mins:02d} мин"
    else:
        label = f"{hours} ч {mins:02d} мин"
    return minutes, label


def time_only(value: str | None) -> str | None:
    dt = parse_dt(value)
    if dt is not None:
        return dt.strftime("%H:%M")
    if not value:
        return None
    # Safe fallback for ISO-ish strings.
    if "T" in value:
        return value.split("T", 1)[1][:5]
    return value


def date_only(value: str | None) -> str | None:
    dt = parse_dt(value)
    if dt is not None:
        return dt.date().isoformat()
    if not value:
        return None
    return value[:10]


def coupe_offer(route: Any, group: Any, travel_date: date) -> dict[str, Any]:
    duration_minutes, duration = duration_info(route.departure_time, route.arrival_time)
    return {
        "date": travel_date.isoformat(),
        "train_number": route.display_number or route.number,
        "price": group.min_price,
        "available_places": group.available_places,
        "departure_time": time_only(route.departure_time),
        "departure_datetime": route.departure_time,
        "arrival_time": time_only(route.arrival_time),
        "arrival_date": date_only(route.arrival_time),
        "arrival_datetime": route.arrival_time,
        "duration_minutes": duration_minutes,
        "duration": duration,
        "provider": route.provider,
    }


def offers_for_routes(routes: list[Any], travel_date: date) -> list[dict[str, Any]]:
    offers: list[dict[str, Any]] = []
    for route in routes:
        for group in route.car_groups:
            if not is_coupe(group.car_type):
                continue
            if group.min_price is None:
                continue
            if group.available_places is not None and group.available_places <= 0:
                continue
            offers.append(coupe_offer(route, group, travel_date))
    # Cheapest first. At equal price prefer shorter travel, then more available places.
    offers.sort(
        key=lambda x: (
            float(x["price"]),
            x["duration_minutes"] if x["duration_minutes"] is not None else 10**9,
            -(x["available_places"] or 0),
        )
    )
    return offers


def main() -> int:
    req = load_request()
    start: date = req["date_from"]
    fetched_at = datetime.now(timezone.utc).isoformat()

    output: dict[str, Any] = {
        "request": {
            "from": req["from"],
            "to": req["to"],
            "date_from": start.isoformat(),
            "days": req["days"],
            "top_per_day": req["top_per_day"],
            "overall_top": req["overall_top"],
            "car_type": "Купе",
        },
        "fetched_at": fetched_at,
        "source": "ticket.rzd.ru via rzd-api 3.0.0",
        "days": [],
        "overall_top": [],
    }

    all_offers: list[dict[str, Any]] = []

    with RzdClient() as client:
        origin_code = client.resolve_station_code(req["from"])
        destination_code = client.resolve_station_code(req["to"])
        output["station_codes"] = {"from": origin_code, "to": destination_code}

        for offset in range(req["days"]):
            travel_date = start + timedelta(days=offset)
            row: dict[str, Any] = {"date": travel_date.isoformat()}
            try:
                routes = client.search_tickets(
                    origin_code,
                    destination_code,
                    travel_date,
                    adults=1,
                    children=0,
                    only_with_seats=True,
                )
                offers = offers_for_routes(routes, travel_date)
                top = offers[: req["top_per_day"]]
                for idx, offer in enumerate(top, start=1):
                    offer["rank_for_day"] = idx
                row.update(
                    {
                        "status": "ok",
                        "train_count": len(routes),
                        "coupe_offer_count": len(offers),
                        "top_coupe": top,
                    }
                )
                all_offers.extend(offers)
            except Exception as exc:
                row.update(
                    {
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "top_coupe": [],
                    }
                )
            output["days"].append(row)

    all_offers.sort(
        key=lambda x: (
            float(x["price"]),
            x["duration_minutes"] if x["duration_minutes"] is not None else 10**9,
            x["date"],
        )
    )
    overall = all_offers[: req["overall_top"]]
    for idx, offer in enumerate(overall, start=1):
        offer["overall_rank"] = idx
    output["overall_top"] = overall

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}: {len(output['days'])} days, {len(overall)} overall offers")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
