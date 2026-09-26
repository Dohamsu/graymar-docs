"""Regression tests for the playtest gate's comparable-run window."""

import unittest

from playtest_gate_ledger import select_gate_window


class GateWindowTests(unittest.TestCase):
    def test_excludes_older_server_versions_before_pooled_judgment(self):
        runs = [
            {"runId": "old-fail", "server": "old", "coreOver": 1},
            {"runId": "current-a", "server": "current", "coreOver": 0},
            {"runId": "older-fail", "server": "old", "coreOver": 1},
            {"runId": "current-b", "server": "current", "coreOver": 0},
        ]

        self.assertEqual(
            [row["runId"] for row in select_gate_window(runs, "current", 3)],
            ["current-a", "current-b"],
        )

    def test_unknown_server_version_cannot_pool_unrelated_runs(self):
        runs = [
            {"runId": "remote-a", "server": "", "coreOver": 1},
            {"runId": "remote-b", "server": "", "coreOver": 0},
        ]

        self.assertEqual(
            [row["runId"] for row in select_gate_window(runs, "", 3)],
            ["remote-b"],
        )


if __name__ == "__main__":
    unittest.main()
