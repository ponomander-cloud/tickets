from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from api.search import COMMITS_URL, CONTENTS_URL, load_snapshot


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


if __name__ == "__main__":
    unittest.main()
