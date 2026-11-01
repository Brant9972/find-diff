"""A previously rejected Zhang Huai-chiu portrait cannot re-enter source search."""
import json
import unittest
from urllib.parse import unquote
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ZhangHuaiChiuSourceTest(unittest.TestCase):
    def test_selected_person_has_exact_qid_and_source_only_review(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(p for p in plan['selectedNew']
                      if p['plannedQuestionId'] == 't1500_0445')
        self.assertEqual(person['name'], '張懷秋')
        self.assertEqual(person['canonicalWikidataQid'], 'Q9138397')
        self.assertNotIn('大嘴巴懷秋.JPG', person['reviewExactCommonsFiles'])
        self.assertIn('https://commons.wikimedia.org/wiki/File:大嘴巴懷秋.JPG',
                      person['excludedPhotoSources'])
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

        legacy_review = json.loads((ROOT.parent / 'photo-review.json').read_text(encoding='utf-8'))
        prior = [item for item in legacy_review['rejected']
                 if item.get('name') == '張懷秋'
                 and '大嘴巴懷秋' in unquote(item.get('source', ''))]
        self.assertEqual(len(prior), 1)
        self.assertEqual(prior[0]['reason'], '閉眼')
        self.assertEqual(prior[0]['reviewedAt'], '2026-10-21')
        self.assertFalse(record['eligibleForLive'])


if __name__ == '__main__':
    unittest.main()
