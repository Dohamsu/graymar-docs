"""Regression tests for the playtest gate's comparable-run window."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from playtest_gate_ledger import make_gate_cohort, select_gate_window


class GateWindowTests(unittest.TestCase):
    def test_excludes_older_server_versions_before_pooled_judgment(self):
        runs = [
            {"runId": "old-fail", "server": "old", "cohort": "same", "coreOver": 1},
            {"runId": "current-a", "server": "current", "cohort": "same", "coreOver": 0},
            {"runId": "older-fail", "server": "old", "cohort": "same", "coreOver": 1},
            {"runId": "current-b", "server": "current", "cohort": "same", "coreOver": 0},
        ]

        self.assertEqual(
            [row["runId"] for row in select_gate_window(runs, "current", "same", 3)],
            ["current-a", "current-b"],
        )

    def test_excludes_same_server_with_different_content_or_model(self):
        runs = [
            {"runId": "old-content", "server": "current", "cohort": "before"},
            {"runId": "new-content", "server": "current", "cohort": "after"},
            {"runId": "old-model", "server": "current", "cohort": "before"},
        ]

        self.assertEqual(
            [row["runId"] for row in select_gate_window(runs, "current", "after", 3)],
            ["new-content"],
        )

    def test_unknown_server_version_cannot_pool_unrelated_runs(self):
        runs = [
            {"runId": "remote-a", "server": "", "cohort": "same", "coreOver": 1},
            {"runId": "remote-b", "server": "", "cohort": "same", "coreOver": 0},
        ]

        self.assertEqual(
            [row["runId"] for row in select_gate_window(runs, "", "same", 3)],
            ["remote-b"],
        )

    def test_unknown_cohort_cannot_pool_same_server_runs(self):
        runs = [
            {"runId": "unknown-a", "server": "current", "cohort": ""},
            {"runId": "unknown-b", "server": "current", "cohort": ""},
        ]
        self.assertEqual(
            [row["runId"] for row in select_gate_window(runs, "current", "", 3)],
            ["unknown-b"],
        )

    def test_cohort_changes_with_pack_json_and_model_settings(self):
        with TemporaryDirectory() as tmp:
            pack = Path(tmp)
            (pack / "scenario.json").write_text('{"hook":"old"}', encoding="utf-8")
            settings = {
                "provider": "openai", "openaiModel": "solar", "claudeModel": "sonnet",
                "geminiModel": "flash", "maxRetries": 2, "timeoutMs": 8000,
                "maxTokens": 1024, "temperature": 0.8,
                "fallbackProvider": "mock", "fallbackModel": "",
            }
            flags = {
                "LLM_ALTERNATE_MODEL": "luna", "LLM_MAIN_ALTERNATE_MODEL": None,
                "LLM_DIALOGUE_MODEL": "nano", "LLM_LIGHT_MODEL": "nano",
            }
            run = {"scenario": "graymar_v1", "preset": "HERBALIST", "agent": "chatty"}
            before = make_gate_cohort("server-a", "start-a", pack, settings, flags, run)
            (pack / "scenario.json").write_text('{"hook":"new"}', encoding="utf-8")
            after_content = make_gate_cohort("server-a", "start-a", pack, settings, flags, run)
            after_model = make_gate_cohort("server-a", "start-a", pack, {**settings, "openaiModel": "other"}, flags, run)
            after_claude = make_gate_cohort("server-a", "start-a", pack, {**settings, "claudeModel": "other"}, flags, run)
            after_temperature = make_gate_cohort("server-a", "start-a", pack, {**settings, "temperature": 0.7}, flags, run)
            after_alternate = make_gate_cohort("server-a", "start-a", pack, settings, {**flags, "LLM_ALTERNATE_MODEL": "other"}, run)
            after_restart = make_gate_cohort("server-a", "start-b", pack, settings, flags, run)
            after_preset = make_gate_cohort("server-a", "start-a", pack, settings, flags, {**run, "preset": "DESERTER"})
            incomplete_flags = make_gate_cohort("server-a", "start-a", pack, settings, {"LLM_ALTERNATE_MODEL": "luna"}, run)

        self.assertTrue(before)
        self.assertNotEqual(before, after_content)
        self.assertNotEqual(after_content, after_model)
        self.assertNotEqual(after_content, after_claude)
        self.assertNotEqual(after_content, after_temperature)
        self.assertNotEqual(after_content, after_alternate)
        self.assertNotEqual(after_content, after_restart)
        self.assertNotEqual(after_content, after_preset)
        self.assertEqual(incomplete_flags, "")


if __name__ == "__main__":
    unittest.main()
