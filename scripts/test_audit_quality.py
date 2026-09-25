import importlib.util
import re
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name('audit_quality.py')
SPEC = importlib.util.spec_from_file_location('audit_quality', SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class PackPhaseAuditTest(unittest.TestCase):
    def test_loads_forbidden_terms_from_pack_content(self):
        rules = AUDIT.load_pack_phase_forbidden('star_sand_v1')

        self.assertEqual(rules['DAY'], ['햇살', '햇빛', '밝은 낮'])

    def test_flags_positive_forbidden_light_description(self):
        prompt = '[현재 시간대] 낮 (DAY)\n- 극야 — 낮에도 해가 뜨지 않는다.'
        issues = AUDIT.classify_pack_phase_terms(
            10,
            '골목 끝으로 햇빛이 얇게 번지고 있었다.',
            prompt,
            'star_sand_v1',
            {'DAY': ['햇빛']},
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'real')
        self.assertEqual(issues[0][1]['cat'], 'pack_phase_forbidden')

    def test_treats_explicit_absence_as_false_positive(self):
        prompt = '[현재 시간대] 낮 (DAY)'
        issues = AUDIT.classify_pack_phase_terms(
            4,
            '두꺼운 구름 아래에는 햇빛이 전혀 들지 않는다.',
            prompt,
            'star_sand_v1',
            {'DAY': ['햇빛']},
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0][0], 'fp')

    def test_does_not_apply_a_different_phase_rule(self):
        issues = AUDIT.classify_pack_phase_terms(
            7,
            '등불이 길게 흔들린다.',
            '[현재 시간대] 밤 (NIGHT)',
            'star_sand_v1',
            {'DAY': ['햇빛']},
        )

        self.assertEqual(issues, [])


class DialogueAndWorldAuditTest(unittest.TestCase):
    def test_hangul_number_coin_and_chopsticks_with_particles_are_detected(self):
        self.assertIsNotNone(re.search(AUDIT.CURRENCY_FORBID['닢'], '스물여섯 닢이 모자랐다'))
        self.assertIsNotNone(re.search(AUDIT.CURRENCY_FORBID['은전'], '은전 몇 개가 손바닥에 놓였다'))
        self.assertIsNotNone(re.search(AUDIT.CURRENCY_FORBID['은화'], '은화를 건넸다'))
        self.assertIsNotNone(re.search(AUDIT.EASTERN_FORBID['젓가락'], '젓가락을 내려놓았다'))

    def test_marker_coverage_uses_the_same_dialogue_denominator(self):
        text = '그가 말했다. @[로넨] "왔군."\n\n@[행인] “조용히.”'
        self.assertEqual(AUDIT.count_dialogue_markers(text), (2, 2))
        self.assertEqual(AUDIT.count_dialogue_markers('문서에 "A"라고 썼다.'), (0, 0))

    def test_bare_colon_speech_is_reviewed_without_treating_narration_as_dialogue(self):
        text = (
            '목소리 큰 생선상인: 조심하오.\n'
            '장부: 열 항목이 있다.\n'
            '낡은 종이에는 날짜: 보름 전이라고 적혀 있다.\n'
            '@[로넨] "왔군."'
        )
        issues = AUDIT.find_bare_colon_dialogue_candidates(5, text)
        self.assertEqual(
            [it['keyword'] for it in issues],
            ['목소리 큰 생선상인', '장부', '낡은 종이에는 날짜'],
        )
        self.assertEqual([it['cat'] for it in issues], ['bare_colon_speech'] * 3)
        self.assertEqual(AUDIT.count_dialogue_markers(text), (1, 1))

    def test_more_than_two_distinct_marked_speakers_is_reported(self):
        text = (
            '@[노부인|NPC_A] "그만하오."\n'
            '@[노부인|NPC_A] "들으시오."\n'
            '@[상인|NPC_B] "조심하오."\n'
            '@[노동자|NPC_C] "물러나시오."'
        )
        issue = AUDIT.find_speaker_cap_issue(6, text)
        self.assertIsNotNone(issue)
        self.assertEqual(issue['cat'], 'speaker_cap')
        self.assertEqual(issue['speaker_count'], 3)
        self.assertIsNone(AUDIT.find_speaker_cap_issue(7, text.splitlines()[0]))


if __name__ == '__main__':
    unittest.main()
