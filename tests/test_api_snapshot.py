from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from api.search import COMMITS_URL, CONTENTS_URL, handler, load_snapshot


class SnapshotSourceTests(unittest.TestCase):
    @patch("api.search.requests.get")
    def test_snapshot_is_loaded_from_current_main_commit(self, get: Mock) -> None:
        commit_response = Mock()
        commit_response.json.return_value = {"sha": "fresh-main-sha"}
        content_response = Mock()
        content_response.json.return_value = {"fetched_at": "new"}
        get.side_effect = [commit_response, content_response]

        result = load_snapshot()

        self.assertEqual(result, {"fetched_at": "new"})
        self.assertEqual(get.call_args_list[0].args[0], COMMITS_URL)
        self.assertEqual(get.call_args_list[1].args[0], CONTENTS_URL)
        self.assertEqual(get.call_args_list[1].kwargs["params"]["ref"], "fresh-main-sha")
        self.assertIn("cachebust", get.call_args_list[0].kwargs["params"])
        self.assertIn("cachebust", get.call_args_list[1].kwargs["params"])
        self.assertEqual(
            get.call_args_list[1].kwargs["headers"]["Accept"],
            "application/vnd.github.raw+json",
        )


class RefreshHandlerTests(unittest.TestCase):
    def make_handler(self, path: str) -> handler:
        request_handler = handler.__new__(handler)
        request_handler.path = path
        request_handler._json = Mock()
        return request_handler

    @patch("api.search.dispatch_refresh")
    @patch("api.search.load_snapshot")
    def test_refresh_dispatches_when_snapshot_does_not_match(
        self, load_snapshot_mock: Mock, dispatch_refresh_mock: Mock
    ) -> None:
        load_snapshot_mock.return_value = {
            "fetched_at": "2026-08-17T10:00:00+00:00",
            "request": {
                "from": "Москва",
                "to": "Адлер",
                "date_from": "2026-08-15",
                "days": 14,
                "top_per_day": 3,
                "overall_top": 10,
            },
        }
        request_handler = self.make_handler(
            "/api/search?from=Адлер&to=Москва&date_from=2026-08-22"
            "&days=7&top_per_day=3&overall_top=10&refresh=true"
        )

        request_handler.do_GET()

        expected_params = {
            "from": "Адлер",
            "to": "Москва",
            "date_from": "2026-08-22",
            "days": "7",
            "top_per_day": "3",
            "overall_top": "10",
            "same_coupe": "0",
        }
        dispatch_refresh_mock.assert_called_once_with(expected_params, None)
        request_handler._json.assert_called_once_with(
            202,
            {"status": "refresh_started", "previous_fetched_at": None},
        )

    @patch("api.search.dispatch_refresh")
    @patch("api.search.load_snapshot")
    def test_refresh_keeps_previous_timestamp_for_matching_snapshot(
        self, load_snapshot_mock: Mock, dispatch_refresh_mock: Mock
    ) -> None:
        params = {
            "from": "Москва",
            "to": "Адлер",
            "date_from": "2026-08-15",
            "days": 14,
            "top_per_day": 3,
            "overall_top": 10,
            "same_coupe": 0,
        }
        load_snapshot_mock.return_value = {
            "fetched_at": "2026-08-17T10:00:00+00:00",
            "request": params,
        }
        request_handler = self.make_handler(
            "/api/search?from=Москва&to=Адлер&date_from=2026-08-15"
            "&days=14&top_per_day=3&overall_top=10&refresh=true"
        )

        request_handler.do_GET()

        dispatch_refresh_mock.assert_called_once_with(
            {key: str(value) for key, value in params.items()},
            "2026-08-17T10:00:00+00:00",
        )
        request_handler._json.assert_called_once_with(
            202,
            {
                "status": "refresh_started",
                "previous_fetched_at": "2026-08-17T10:00:00+00:00",
            },
        )

    @patch("api.search.dispatch_refresh")
    @patch("api.search.load_snapshot")
    def test_non_refresh_still_requires_matching_snapshot(
        self, load_snapshot_mock: Mock, dispatch_refresh_mock: Mock
    ) -> None:
        load_snapshot_mock.return_value = {
            "fetched_at": "2026-08-17T10:00:00+00:00",
            "request": {
                "from": "Москва",
                "to": "Адлер",
                "date_from": "2026-08-15",
                "days": 14,
                "top_per_day": 3,
            "overall_top": 10,
            "same_coupe": 0,
            },
        }
        request_handler = self.make_handler(
            "/api/search?from=Адлер&to=Москва&date_from=2026-08-22"
            "&days=7&top_per_day=3&overall_top=10"
        )

        request_handler.do_GET()

        dispatch_refresh_mock.assert_not_called()
        request_handler._json.assert_called_once_with(
            409,
            {"error": "No snapshot exists for this request; use refresh=true"},
        )


if __name__ == "__main__":
    unittest.main()
