from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from rzd_search import add_value_scores, unique_coupe_offers


def group(car_type: str, price: float, places: int) -> SimpleNamespace:
    return SimpleNamespace(car_type=car_type, min_price=price, available_places=places)


def route(number: str, groups: list[SimpleNamespace], duration_hours: int = 30) -> SimpleNamespace:
    day = 16 if duration_hours >= 24 else 15
    hour = duration_hours % 24
    return SimpleNamespace(
        display_number=number,
        number=number,
        departure_time="2026-08-15T00:00:00",
        arrival_time=f"2026-08-{day:02d}T{hour:02d}:00:00",
        car_groups=groups,
    )


class SearchTests(unittest.TestCase):
    def test_deduplicates_train_and_sums_equal_cheapest_groups(self) -> None:
        routes = [
            route("001А", [group("Купе", 5000, 2), group("compartment", 5000, 3), group("Купе", 6000, 9)]),
            route("002Б", [group("Купе", 4500, 1)]),
            route("001А", [group("Купе", 5200, 8)]),
            route("003В", [group("Плацкарт", 1000, 20)]),
        ]
        offers = unique_coupe_offers(routes, date(2026, 8, 15))
        self.assertEqual([item["train_number"] for item in offers], ["002Б", "001А"])
        self.assertEqual(offers[1]["price"], 5000.0)
        self.assertEqual(offers[1]["available_places"], 5)

    def test_sort_tiebreaks_use_duration_then_places(self) -> None:
        routes = [
            route("003В", [group("Купе", 5000, 9)], 35),
            route("001А", [group("Купе", 5000, 2)], 30),
            route("002Б", [group("Купе", 5000, 5)], 30),
        ]
        offers = unique_coupe_offers(routes, date(2026, 8, 15))
        self.assertEqual([item["train_number"] for item in offers], ["002Б", "001А", "003В"])

    def test_value_score_is_normalized_seventy_thirty(self) -> None:
        offers = [
            {"price": 100.0, "duration_minutes": 300},
            {"price": 200.0, "duration_minutes": 100},
        ]
        scored = add_value_scores(offers)
        self.assertEqual(scored[0]["value_score"], 0.3)
        self.assertEqual(scored[1]["value_score"], 0.7)

    def test_search_keeps_scheduled_trains_when_no_seats_are_available(self) -> None:
        class FakeClient:
            calls: list[bool] = []

            def __enter__(self) -> "FakeClient":
                return self

            def __exit__(self, *_: object) -> None:
                pass

            def resolve_station_code(self, station: str) -> str:
                return {"Адлер": "2064150", "Москва": "2000000"}[station]

            def search_tickets(self, *_: object, **kwargs: object) -> list[SimpleNamespace]:
                self.calls.append(bool(kwargs["only_with_seats"]))
                return [
                    route(
                        "104Ж",
                        [group("Купе", 5000, 0)],
                    ),
                    route(
                        "102С",
                        [group("Плацкарт", 3000, 0)],
                    ),
                ]

        from rzd_search import search

        fake = FakeClient()
        result = search(
            {
                "from": "Адлер",
                "to": "Москва",
                "date_from": "2026-08-22",
                "days": 1,
                "top_per_day": 3,
                "overall_top": 10,
            },
            client_factory=lambda: fake,
        )

        self.assertEqual(fake.calls, [False])
        self.assertEqual(result["days"][0]["train_count"], 2)
        self.assertEqual(result["days"][0]["coupe_train_count"], 0)


if __name__ == "__main__":
    unittest.main()
