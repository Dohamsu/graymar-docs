"""A goal-directed player can follow the authored graymar finale path."""

import unittest

from playtest_finale_route import choose_finale_input


STAGES = ["LOC_MARKET", "LOC_GUARD", "LOC_GUARD"]


def state(node, quest="S1_GET_ANGLE", facts=(), location="LOC_MARKET", arc=None):
    return {
        "currentNode": {"nodeType": node},
        "runState": {
            "questState": quest,
            "discoveredQuestFacts": list(facts),
            "worldState": {"currentLocationId": location},
            "arcState": arc or {},
        },
    }


class FinaleRoutePlayerTests(unittest.TestCase):
    def test_accepts_quest_then_visits_market_for_missing_facts(self):
        hub = state("HUB")
        self.assertEqual(
            choose_finale_input(hub, [{"id": "accept_quest"}], STAGES),
            {"type": "CHOICE", "choiceId": "accept_quest"},
        )
        self.assertEqual(
            choose_finale_input(hub, [{"id": "go_market"}], STAGES),
            {"type": "CHOICE", "choiceId": "go_market"},
        )

    def test_asks_for_the_next_missing_authored_fact(self):
        market = state("LOCATION", facts=["FACT_LEDGER_EXISTS", "FACT_WAGE_FRAUD_PATTERN"])
        decision = choose_finale_input(market, [], STAGES)
        self.assertEqual(decision["type"], "ACTION")
        self.assertIn("셋째 칸 넷째 줄", decision["text"])

    def test_commits_at_s3_then_tracks_each_stage_location(self):
        hub = state("HUB", quest="S3_TRACE_ROUTE")
        self.assertEqual(
            choose_finale_input(hub, [{"id": "arc_commit_expose_corruption"}], STAGES),
            {"type": "CHOICE", "choiceId": "arc_commit_expose_corruption"},
        )
        arc = {"currentRoute": "EXPOSE_CORRUPTION", "committedAt": 15, "stageProgress": {"completedStages": [1]}}
        self.assertEqual(
            choose_finale_input(state("LOCATION", quest="S3_TRACE_ROUTE", arc=arc), [], STAGES),
            {"type": "ACTION", "text": "다른 장소로 이동한다"},
        )
        self.assertEqual(
            choose_finale_input(state("HUB", quest="S3_TRACE_ROUTE", arc=arc), [{"id": "go_guard"}], STAGES),
            {"type": "CHOICE", "choiceId": "go_guard"},
        )

    def test_finale_choice_wins_after_stage_completion(self):
        arc = {"currentRoute": "EXPOSE_CORRUPTION", "committedAt": 15, "stageProgress": {"completedStages": [1, 2, 3], "finaleReady": True}}
        self.assertEqual(
            choose_finale_input(state("LOCATION", quest="S4_CONFRONT", arc=arc), [{"id": "arc_finale"}], STAGES),
            {"type": "CHOICE", "choiceId": "arc_finale"},
        )


if __name__ == "__main__":
    unittest.main()
