"""Curated identity exclusions must survive every media search batch."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare_media import merge_caption_exclusions


class CaptionExclusionsPersistenceTest(unittest.TestCase):
    def test_curated_names_survive_transient_review_reason(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        wang = next(p for p in plan['selectedNew']
                    if p['plannedQuestionId'] == 't1500_0007')
        self.assertEqual(wang['wikidataId'], 'Q9066373')
        before = list(wang['excludedCaptionNames'])
        merged = merge_caption_exclusions(wang, '舊照片涉及其他人；再次涉及王童')
        self.assertEqual(merged[:len(before)], before)
        self.assertEqual(merged.count('王童'), 1)
        self.assertIn('其他人', merged)
        self.assertIn('王彤', merged)
        self.assertIn('王統', merged)
        self.assertEqual(wang['excludedCaptionNames'], before,
                         'Do not mutate the authoritative release-plan row')

    def test_empty_reason_does_not_clear_prior_rejections(self):
        self.assertEqual(merge_caption_exclusions(
            {'excludedCaptionNames': ['黃芷晴', '王童']}, ''),
            ['黃芷晴', '王童'])
        self.assertEqual(merge_caption_exclusions(
            {'excludedCaptionNames': ['王童', '王童', '']},
            '涉及王彤；涉及王童'), ['王童', '王彤'])
        self.assertEqual(merge_caption_exclusions({}, '無新增資訊'), [])


if __name__ == '__main__':
    unittest.main()
