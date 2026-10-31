"""Review evidence is immutable and cannot imply an automatic live release."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HuangShaoKuReviewedTest(unittest.TestCase):
    def test_review_is_sha_pinned_and_pending_integration(self):
        review = json.loads((ROOT / 'pipeline/chatgpt-review/20261031-huangshaoku-v2-reviewed.json')
                            .read_text(encoding='utf-8'))
        self.assertEqual(review['releaseGate'], 'HUMAN_PHOTO_APPROVED_PENDING_INTEGRATION_QA')
        self.assertEqual(len(review['decisions']), 1)
        item = review['decisions'][0]
        self.assertEqual(item['personId'], 't1500_0108')
        self.assertFalse(item['eligibleForLive'])
        self.assertEqual(item['gameSha256'],
                         '640dca1277207e65cf27e5a2278afc36f689c7af358364324c9d13bfc4164ab9')
        self.assertEqual(item['license'], 'CC BY-SA 4.0')
        self.assertEqual(item['reveal']['mouth'][3], .55)
        self.assertEqual(item['reveal']['chin'][3], .62)
        self.assertIn('https://music-tw.line.me/album/1370542', item['workSource'])


if __name__ == '__main__':
    unittest.main()
