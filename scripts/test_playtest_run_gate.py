"""A server 500 must not be hidden by later successful turns."""

import unittest

from playtest_run_gate import turns_executed_pass


class TurnExecutionTests(unittest.TestCase):
    def test_full_run_without_submission_errors_passes(self):
        self.assertTrue(turns_executed_pass(30, 30, False, []))

    def test_server_error_fails_even_after_enough_successful_turns(self):
        self.assertFalse(turns_executed_pass(29, 30, False, [{"turn": 23, "status": 500}]))

    def test_natural_early_ending_passes_without_errors(self):
        self.assertTrue(turns_executed_pass(23, 30, True, []))

    def test_points_exhaustion_also_fails(self):
        self.assertFalse(turns_executed_pass(29, 30, False, [{"turn": 30, "status": 402}]))


if __name__ == "__main__":
    unittest.main()
