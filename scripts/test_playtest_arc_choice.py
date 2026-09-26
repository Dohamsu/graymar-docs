"""The playtest must click the finale even after a separate route commit."""

import unittest

from playtest_arc_choice import select_priority_arc_choice


class PriorityArcChoiceTests(unittest.TestCase):
    def test_commits_route_once(self):
        choice = {"id": "arc_commit_expose_corruption"}
        self.assertEqual(select_priority_arc_choice([choice], False), choice)
        self.assertIsNone(select_priority_arc_choice([choice], True))

    def test_finale_stays_available_after_route_commit(self):
        finale = {"id": "arc_finale"}
        commit = {"id": "arc_commit_expose_corruption"}
        self.assertEqual(select_priority_arc_choice([commit, finale], True), finale)
        self.assertEqual(select_priority_arc_choice([commit, finale], False), finale)


if __name__ == "__main__":
    unittest.main()
