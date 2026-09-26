"""A goal-directed player can follow the authored graymar finale path."""

import unittest
import json
from pathlib import Path

from playtest_finale_route import ROUTE_STAGE_ACTIONS, choose_finale_input, finale_fallback_choices, verify_finale_route


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
    def test_each_authored_stage_has_action_cues_matched_by_its_driver(self):
        content = json.loads((Path(__file__).resolve().parent.parent / "content/graymar_v1/arc_events.json").read_text())
        for route, actions in ROUTE_STAGE_ACTIONS.items():
            stages = sorted(content[route], key=lambda item: item["stage"])
            self.assertEqual(len(stages), len(actions))
            for stage, action in zip(stages, actions):
                cues = stage.get("progressCues") or []
                self.assertTrue(cues, f"{route} stage {stage['stage']} has no progress cues")
                self.assertTrue(stage.get("completionSummary"),
                                f"{route} stage {stage['stage']} has no completion summary")
                self.assertTrue(any(all(cue in action for cue in group) for group in cues),
                                f"{route} stage {stage['stage']} driver action does not match")

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

    def test_profit_route_commits_its_own_choice_and_follows_harbor_stage(self):
        stages = ["LOC_HARBOR", "LOC_SLUMS", "LOC_SLUMS"]
        hub = state("HUB", quest="S3_TRACE_ROUTE")
        choices = [{"id": "arc_commit_expose_corruption"}, {"id": "arc_commit_profit_from_chaos"}]
        self.assertEqual(
            choose_finale_input(hub, choices, stages, "PROFIT_FROM_CHAOS"),
            {"type": "CHOICE", "choiceId": "arc_commit_profit_from_chaos"},
        )
        arc = {"currentRoute": "PROFIT_FROM_CHAOS", "committedAt": 15, "stageProgress": {"completedStages": []}}
        self.assertEqual(
            choose_finale_input(state("HUB", quest="S3_TRACE_ROUTE", arc=arc), [{"id": "go_harbor"}], stages, "PROFIT_FROM_CHAOS"),
            {"type": "CHOICE", "choiceId": "go_harbor"},
        )
        action = choose_finale_input(state("LOCATION", quest="S3_TRACE_ROUTE", location="LOC_HARBOR", arc=arc), [], stages, "PROFIT_FROM_CHAOS")
        self.assertIn("밀수 경로", action["text"])

    def test_guard_route_uses_guard_stage_not_expose_action(self):
        arc = {"currentRoute": "ALLY_GUARD", "committedAt": 15, "stageProgress": {"completedStages": [1]}}
        action = choose_finale_input(
            state("LOCATION", quest="S4_CONFRONT", location="LOC_GUARD", arc=arc),
            [], ["LOC_GUARD", "LOC_GUARD", "LOC_GUARD"], "ALLY_GUARD",
        )
        self.assertIn("야간 순찰", action["text"])
        self.assertNotIn("찢긴 교대표와 장부 조작 증거", action["text"])

    def test_other_route_commit_cannot_be_taken_by_generic_fallback(self):
        choices = [{"id": "arc_commit_expose_corruption"}, {"id": "arc_finale"}, {"id": "go_market"}]
        self.assertEqual(finale_fallback_choices(choices), [{"id": "go_market"}])

    def test_wrong_committed_route_aborts_goal_directed_driver(self):
        arc = {"currentRoute": "EXPOSE_CORRUPTION", "committedAt": 15}
        with self.assertRaisesRegex(ValueError, "expected PROFIT_FROM_CHAOS"):
            choose_finale_input(state("HUB", quest="S4_CONFRONT", arc=arc), [], ["LOC_HARBOR"], "PROFIT_FROM_CHAOS")

    def test_finale_report_checks_actual_route_and_explicit_end(self):
        arc = {"currentRoute": "PROFIT_FROM_CHAOS", "stageProgress": {"completedStages": [1, 2, 3]}}
        terminal = {"input": "FINALE:arc_finale", "nodeOutcome": "RUN_ENDED", "endingResult": {"arcRoute": "PROFIT_FROM_CHAOS"}}
        good = verify_finale_route("PROFIT_FROM_CHAOS", arc, [terminal])
        self.assertTrue(good["pass"])
        self.assertEqual(good["completedStages"], [1, 2, 3])
        bad = verify_finale_route("ALLY_GUARD", arc, [terminal])
        self.assertFalse(bad["pass"])

    def test_full_mode_rejects_early_safety_net_and_driver_continues(self):
        arc = {"currentRoute": "PROFIT_FROM_CHAOS", "committedAt": 15,
               "stageProgress": {"completedStages": [1], "finaleReady": True}}
        terminal = {"input": "FINALE:arc_finale", "nodeOutcome": "RUN_ENDED",
                    "questStateBefore": "S5_RESOLVE",
                    "endingResult": {"arcRoute": "PROFIT_FROM_CHAOS"}}
        self.assertFalse(verify_finale_route("PROFIT_FROM_CHAOS", arc, [terminal])["pass"])
        self.assertTrue(verify_finale_route("PROFIT_FROM_CHAOS", arc, [terminal], "early", "S5_RESOLVE")["pass"])
        premature = {**terminal, "questStateBefore": "S4_CONFRONT"}
        self.assertFalse(verify_finale_route("PROFIT_FROM_CHAOS", arc, [premature], "early", "S5_RESOLVE")["pass"])
        action = choose_finale_input(state("HUB", quest="S5_RESOLVE", arc=arc),
                                     [{"id": "arc_finale"}, {"id": "go_slums"}],
                                     ["LOC_HARBOR", "LOC_SLUMS", "LOC_SLUMS"],
                                     "PROFIT_FROM_CHAOS")
        self.assertEqual(action, {"type": "CHOICE", "choiceId": "go_slums"})

    def test_early_driver_ignores_premature_finale_choice_before_s5(self):
        arc = {"currentRoute": "EXPOSE_CORRUPTION", "committedAt": 15,
               "stageProgress": {"completedStages": []}}
        action = choose_finale_input(
            state("LOCATION", quest="S4_CONFRONT", location="LOC_GUARD", arc=arc),
            [{"id": "arc_finale"}], STAGES, "EXPOSE_CORRUPTION", "early",
        )
        self.assertEqual(action["type"], "ACTION")
        self.assertIn("비공식 내사", action["text"])

    def test_early_driver_does_not_complete_authored_stage(self):
        arc = {"currentRoute": "PROFIT_FROM_CHAOS", "committedAt": 15,
               "stageProgress": {"completedStages": [], "announcedStages": [1]}}
        action = choose_finale_input(state("LOCATION", quest="S5_RESOLVE", location="LOC_GUARD", arc=arc),
                                     [], ["LOC_HARBOR", "LOC_SLUMS", "LOC_SLUMS"],
                                     "PROFIT_FROM_CHAOS", "early")
        self.assertIn("거래도 시작하지 않고", action["text"])
        self.assertNotIn("구입하고", action["text"])

    def test_early_driver_reaches_terminal_quest_without_stage_trade(self):
        arc = {"currentRoute": "EXPOSE_CORRUPTION", "committedAt": 15,
               "stageProgress": {"completedStages": []}}
        for quest, location, fragment in [
            ("S3_TRACE_ROUTE", "LOC_HARBOR", "야간 하역"),
            ("S4_CONFRONT", "LOC_GUARD", "비공식 내사"),
        ]:
            action = choose_finale_input(state("LOCATION", quest=quest, location=location, arc=arc),
                                         [], STAGES, "EXPOSE_CORRUPTION", "early")
            self.assertIn(fragment, action["text"])
            self.assertNotIn("교대표", action["text"])


if __name__ == "__main__":
    unittest.main()
