import importlib.util
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


if __name__ == '__main__':
    unittest.main()
