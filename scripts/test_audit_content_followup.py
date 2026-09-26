import unittest

from audit_content import Pack, check_l2_contract


class FactFollowUpContractTests(unittest.TestCase):
    def test_location_and_item_display_currency_are_audited(self):
        pack = Pack("graymar_v1")
        pack.raw["locations.json"][0]["name"] = "금화 시장"
        pack.raw["items.json"][0]["description"] = "동전으로 만든 물건"
        findings = [
            finding for finding in check_l2_contract(pack)
            if finding.rule == "NONCANONICAL_CURRENCY"
        ]
        self.assertTrue(any("locations.json" in finding.where for finding in findings))
        self.assertTrue(any("items.json" in finding.where for finding in findings))

    def test_visible_authored_currency_uses_gold_vocabulary(self):
        pack = Pack("graymar_v1")
        event = next(e for e in pack.events if e.get("eventId") == "EVT_GUARD_INT_3")
        event["payload"] = dict(event["payload"], sceneFrame="금화를 건넨다")
        findings = [
            finding
            for finding in check_l2_contract(pack)
            if finding.rule == "NONCANONICAL_CURRENCY"
            and "EVT_GUARD_INT_3" in finding.where
        ]
        self.assertTrue(findings)

    def test_next_fact_question_needs_shared_holder_and_place(self):
        pack = Pack("star_sand_v1")
        target = dict(pack.facts["FACT_SS_SAME_WORDS"])
        target["knownBy"] = []
        pack.facts["FACT_SS_SAME_WORDS"] = target
        rules = {finding.rule for finding in check_l2_contract(pack)}
        self.assertIn("FACT_NEXT_QUESTION_UNREACHABLE", rules)

    def test_reconfirmation_needs_anchored_authored_lines(self):
        pack = Pack("star_sand_v1")
        source = dict(pack.facts["FACT_SS_FIRST_DREAM"])
        source["reconfirm"] = {"NPC_SS_IREN": {"anchors": [], "lines": ["답변"]}}
        pack.facts["FACT_SS_FIRST_DREAM"] = source
        rules = {finding.rule for finding in check_l2_contract(pack)}
        self.assertIn("FACT_RECONFIRM_SHAPE", rules)

    def test_directed_subscene_needs_a_visible_transition_lead(self):
        pack = Pack("graymar_v1")
        event = next(e for e in pack.events if e.get("eventId") == "EVT_GUARD_INT_3")
        event["payload"] = dict(event["payload"], transitionLead="")
        rules = {finding.rule for finding in check_l2_contract(pack)}
        self.assertIn("DIRECTED_SUBSCENE_SHAPE", rules)

    def test_directed_subscene_needs_runtime_arrays(self):
        for key in ("affordances", "gates"):
            pack = Pack("graymar_v1")
            event = next(e for e in pack.events if e.get("eventId") == "EVT_GUARD_INT_3")
            event.pop(key)
            rules = {finding.rule for finding in check_l2_contract(pack)}
            self.assertIn("DIRECTED_SUBSCENE_SHAPE", rules)

    def test_withheld_next_step_must_belong_to_fact_holder(self):
        pack = Pack("graymar_v1")
        fact = dict(pack.facts["FACT_INSIDE_JOB"])
        fact["withheldNextStep"] = {"NPC_RONEN": "경비대에 간다"}
        pack.facts["FACT_INSIDE_JOB"] = fact
        rules = {finding.rule for finding in check_l2_contract(pack)}
        self.assertIn("FACT_WITHHELD_STEP_SHAPE", rules)

    def test_withheld_next_step_anchors_must_appear_in_authored_line(self):
        pack = Pack("graymar_v1")
        fact = dict(pack.facts["FACT_INSIDE_JOB"])
        fact["withheldNextStep"] = {
            "NPC_EDRIC_VEIL": {"line": "경비대에 가시오", "anchors": ["출입 기록"]}
        }
        pack.facts["FACT_INSIDE_JOB"] = fact
        rules = {finding.rule for finding in check_l2_contract(pack)}
        self.assertIn("FACT_WITHHELD_STEP_SHAPE", rules)

    def test_withheld_next_step_target_must_exist_in_pack(self):
        pack = Pack("graymar_v1")
        fact = dict(pack.facts["FACT_INSIDE_JOB"])
        fact["withheldNextStep"] = {
            "NPC_EDRIC_VEIL": {
                "line": "경비대 지구의 출입 기록을 보시오",
                "anchors": ["경비대 지구", "출입 기록"],
                "choiceLabel": "출입 기록을 살핀다",
                "targetLocationId": "LOC_UNKNOWN",
            }
        }
        pack.facts["FACT_INSIDE_JOB"] = fact
        rules = {finding.rule for finding in check_l2_contract(pack)}
        self.assertIn("FACT_WITHHELD_STEP_SHAPE", rules)


if __name__ == "__main__":
    unittest.main()
