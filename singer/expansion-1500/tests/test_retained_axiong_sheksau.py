"""Retained source rejection records must not become playable photos."""
import json
import unittest
from pathlib import Path


class RetainedSourceScreeningTest(unittest.TestCase):
    def test_exact_source_rejections_remain_draft_only(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        people = {row['plannedQuestionId']: row for row in plan['selectedNew']}
        review = json.loads((root / 'pipeline/chatgpt-review/20261031-retained-source-axiong-sheksau.json')
                            .read_text(encoding='utf-8'))
        self.assertEqual(review['releaseGate'], 'DRAFT_ONLY_NOT_PLAYABLE')
        self.assertEqual(review['summary']['approvedForLive'], 0)
        expected = {
            't1500_0099': 'https://commons.wikimedia.org/wiki/File:%E9%98%BF%E7%BF%94.JPG',
            't1500_0552': 'https://commons.wikimedia.org/wiki/File:%E7%9F%B3%E4%BF%AE.jpg',
        }
        self.assertEqual({row['personId'] for row in review['decisions']}, set(expected))
        for row in review['decisions']:
            pid = row['personId']
            self.assertFalse(row['eligibleForLive'])
            self.assertEqual(len(row['originalSha256']), 64)
            self.assertEqual(row['sourcePage'], expected[pid])
            self.assertIn(expected[pid], people[pid]['excludedPhotoSources'])
            self.assertNotEqual(people[pid]['photoStatus'], 'published')
        self.assertEqual(review['decisions'][1]['commonsLicenseReviewStatus'], 'needed')


if __name__ == '__main__':
    unittest.main()
