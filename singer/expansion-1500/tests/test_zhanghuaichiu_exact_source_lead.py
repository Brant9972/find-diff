"""Exact licensed source hint for Zhang Huai-chiu remains non-production."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ZhangHuaiChiuSourceTest(unittest.TestCase):
    def test_selected_person_has_exact_qid_and_source_only_review(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(p for p in plan['selectedNew']
                      if p['plannedQuestionId'] == 't1500_0445')
        self.assertEqual(person['name'], '張懷秋')
        self.assertEqual(person['canonicalWikidataQid'], 'Q9138397')
        self.assertIn('大嘴巴懷秋.JPG', person['reviewExactCommonsFiles'])
        self.assertIn('Harry Chang', person['acceptedAnswers'])
        self.assertNotEqual(person['photoStatus'], 'published')
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        self.assertFalse(person['imageVerification']['rightsDocumented'])

        record = json.loads((ROOT / 'pipeline/chatgpt-review/20261101-zhanghuaichiu-exact-commons-lead.json')
                            .read_text(encoding='utf-8'))
        self.assertEqual(record['releaseGate'], 'SOURCE_ONLY_NOT_PLAYABLE')
        self.assertFalse(record['eligibleForLive'])
        self.assertEqual(record['source']['license'], 'CC BY-SA 3.0 Unported')
        self.assertFalse(record['source']['visualSourcePreview']['fiveStageViewed'])
        self.assertIsNone(record['source']['originalSha1'])


if __name__ == '__main__':
    unittest.main()
