from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from rzd_api import Config, RzdClient
from rzd_api.api import RzdApi
from rzd_api.query import RzdTransport

SOURCE = "ticket.rzd.ru via rzd-api 3.0.0"
KNOWN_STATION_CODES = {
    "москва": "2000000",
    "адлер": "2064150",
}
RZD_ADDRESS_POOL = (
    "212.164.138.120",
    "212.164.138.121",
    "212.164.138.122",
    "212.164.138.123",
    "212.164.138.124",
    "212.164.138.125",
    "212.164.138.126",
    "212.164.138.127",
    "212.164.138.128",
    "212.164.138.129",
    "212.164.138.130",
    "212.164.138.131",
)
RZD_EDGE_RELAY = "https://rzd-tickets-live.vercel.app/api/rzd-proxy"


class RzdAddressPoolSession(requests.Session):
    """Try RZD's published address pool without depending on runtime DNS."""

    def __init__(self) -> None:
        super().__init__()
        self._preferred_address: str | None = None

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        parts = urlsplit(url)
        if parts.hostname != "ticket.rzd.ru":
            return super().request(method, url, **kwargs)

        if os.getenv("VERCEL"):
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["X-RZD-Relay"] = "train-pricing"
            original_timeout = kwargs.pop("timeout", (8.0, 30.0))
            read_timeout = original_timeout[1] if isinstance(original_timeout, tuple) else original_timeout
            return super().request(
                method,
                RZD_EDGE_RELAY,
                headers=headers,
                timeout=(8.0, read_timeout),
                **kwargs,
            )

        addresses = list(RZD_ADDRESS_POOL)
        if self._preferred_address in addresses:
            addresses.remove(self._preferred_address)
            addresses.insert(0, self._preferred_address)

        last_error: requests.RequestException | None = None
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Host"] = "ticket.rzd.ru"
        original_timeout = kwargs.pop("timeout", (8.0, 30.0))
        read_timeout = original_timeout[1] if isinstance(original_timeout, tuple) else original_timeout
        for address in addresses:
            direct_url = urlunsplit((parts.scheme, address, parts.path, parts.query, parts.fragment))
            try:
                response = super().request(
                    method,
                    direct_url,
                    headers=headers,
                    timeout=(2.0, read_timeout),
                    **kwargs,
                )
                self._preferred_address = address
                return response
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
        assert last_error is not None
        raise last_error


def validate_request(values: dict[str, Any]) -> dict[str, Any]:
    origin = str(values.get("from", "")).strip()
    destination = str(values.get("to", "")).strip()
    start = date.fromisoformat(str(values.get("date_from", "")))
    days = int(values.get("days", 14))
    top_per_day = int(values.get("top_per_day", 3))
    overall_top = int(values.get("overall_top", 10))
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
    return bool(car_type) and car_type.strip().casefold() in {
        "compartment",
        "купе",
        "coupe",
        "kupe",
    }


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_info(departure: str | None, arrival: str | None) -> tuple[int | None, str | None]:
    dep = parse_dt(departure)
    arr = parse_dt(arrival)
    if dep is None or arr is None:
        return None, None
    minutes = int((arr - dep).total_seconds() // 60)
    if minutes < 0:
        return None, None
    hours, mins = divmod(minutes, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return minutes, f"{days} д {hours} ч {mins:02d} мин"
    return minutes, f"{hours} ч {mins:02d} мин"


def time_only(value: str | None) -> str | None:
    parsed = parse_dt(value)
    if parsed is not None:
        return parsed.strftime("%H:%M")
    if value and "T" in value:
        return value.split("T", 1)[1][:5]
    return value


def date_only(value: str | None) -> str | None:
    parsed = parse_dt(value)
    if parsed is not None:
        return parsed.date().isoformat()
    return value[:10] if value else None


def _ticket(route: Any, price: float, places: int | None, travel_date: date) -> dict[str, Any]:
    minutes, duration = duration_info(route.departure_time, route.arrival_time)
    return {
        "date": travel_date.isoformat(),
        "train_number": route.display_number or route.number,
        "price": price,
        "available_places": places,
        "departure_time": time_only(route.departure_time),
        "arrival_time": time_only(route.arrival_time),
        "arrival_date": date_only(route.arrival_time),
        "duration": duration,
        "duration_minutes": minutes,
    }


def unique_coupe_offers(routes: list[Any], travel_date: date) -> list[dict[str, Any]]:
    """Return one cheapest coupe offer per train, summing equal-price group availability."""
    groups_by_train: dict[str, list[tuple[Any, Any]]] = {}
    for route in routes:
        train_number = route.display_number or route.number
        if not train_number:
            continue
        for group in route.car_groups:
            if (
                is_coupe(group.car_type)
                and group.min_price is not None
                and (group.available_places is None or group.available_places > 0)
            ):
                groups_by_train.setdefault(str(train_number), []).append((route, group))

    offers: list[dict[str, Any]] = []
    for train_groups in groups_by_train.values():
        cheapest = min(float(group.min_price) for _, group in train_groups)
        cheapest_groups = [(route, group) for route, group in train_groups if float(group.min_price) == cheapest]
        known_places = [
            int(group.available_places)
            for _, group in cheapest_groups
            if group.available_places is not None
        ]
        places = sum(known_places) if known_places else None
        candidates = [_ticket(route, cheapest, places, travel_date) for route, _ in cheapest_groups]
        offers.append(min(candidates, key=_daily_sort_key))
    offers.sort(key=_daily_sort_key)
    return offers


def _daily_sort_key(ticket: dict[str, Any]) -> tuple[float, int, int]:
    return (
        float(ticket["price"]),
        ticket["duration_minutes"] if ticket["duration_minutes"] is not None else 10**9,
        -(ticket["available_places"] or 0),
    )


def _normalized(value: float, minimum: float, maximum: float) -> float:
    return 0.0 if maximum == minimum else (value - minimum) / (maximum - minimum)


def add_value_scores(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not offers:
        return []
    prices = [float(item["price"]) for item in offers]
    durations = [
        float(item["duration_minutes"] if item["duration_minutes"] is not None else 10**9)
        for item in offers
    ]
    price_min, price_max = min(prices), max(prices)
    duration_min, duration_max = min(durations), max(durations)
    scored: list[dict[str, Any]] = []
    for item, price, duration in zip(offers, prices, durations):
        result = dict(item)
        result["value_score"] = round(
            0.7 * _normalized(price, price_min, price_max)
            + 0.3 * _normalized(duration, duration_min, duration_max),
            6,
        )
        scored.append(result)
    return scored


def configured_client() -> RzdClient:
    # Keep timeouts bounded for an on-demand serverless request while using
    # RZD's official endpoint. Endpoint construction and response parsing stay
    # inside rzd-api 3.0.0.
    config = Config(
        base_url="https://ticket.rzd.ru/api/v1",
        connect_timeout=8.0,
        read_timeout=30.0,
        retry_total=0,
        referer="https://ticket.rzd.ru/",
    )
    session = RzdAddressPoolSession()
    transport = RzdTransport(config, session)
    return RzdClient(_api=RzdApi(config, transport))


def search(request_values: dict[str, Any], client_factory: Any = configured_client) -> dict[str, Any]:
    req = validate_request(request_values)
    start: date = req["date_from"]
    request_output = {
        "from": req["from"],
        "to": req["to"],
        "date_from": start.isoformat(),
        "days": req["days"],
        "top_per_day": req["top_per_day"],
        "overall_top": req["overall_top"],
        "car_type": "Купе",
    }
    output: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "request": request_output,
        "days": [],
        "overall_cheapest": [],
        "overall_value": [],
    }
    all_offers: list[dict[str, Any]] = []
    with client_factory() as client:
        # Avoid an extra RZD station-suggestion round trip for the documented route.
        # Other station names are still resolved live through rzd-api.
        origin_code = KNOWN_STATION_CODES.get(req["from"].casefold()) or client.resolve_station_code(req["from"])
        destination_code = KNOWN_STATION_CODES.get(req["to"].casefold()) or client.resolve_station_code(req["to"])
        for offset in range(req["days"]):
            travel_date = start + timedelta(days=offset)
            routes = client.search_tickets(
                origin_code,
                destination_code,
                travel_date,
                adults=1,
                children=0,
                only_with_seats=True,
            )
            offers = unique_coupe_offers(routes, travel_date)
            output["days"].append(
                {
                    "date": travel_date.isoformat(),
                    "train_count": len(routes),
                    "coupe_train_count": len(offers),
                    "top_coupe": offers[: req["top_per_day"]],
                }
            )
            all_offers.extend(offers)

    cheapest = sorted(all_offers, key=lambda item: (*_daily_sort_key(item), item["date"]))
    scored = add_value_scores(all_offers)
    value = sorted(
        scored,
        key=lambda item: (
            item["value_score"],
            float(item["price"]),
            item["duration_minutes"] if item["duration_minutes"] is not None else 10**9,
            item["date"],
        ),
    )
    output["overall_cheapest"] = cheapest[: req["overall_top"]]
    output["overall_value"] = value[: req["overall_top"]]
    return output
