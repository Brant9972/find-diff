"""A visually rejected exact Commons file must never return as a new candidate."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'singer' / 'expansion-1500'))
from media_pipeline.sources import source_key


class HuangHongxuanSourceRejectionTest(unittest.TestCase):
    def test_rejected_exact_source_is_excluded_and_source_pixels_are_auditable(self):
        plan = json.loads((ROOT / 'singer/expansion-1500/release-plan-20261028.json').read_text())
        person = next(p for p in plan['selectedNew']
                      if p['plannedQuestionId'] == 't1500_0534')
        review = json.loads((ROOT / 'singer/expansion-1500/pipeline/chatgpt-review/'
                             '20261031-huanghongxuan-new-source-visual-rejected.json').read_text())
        self.assertEqual(review['personId'], person['plannedQuestionId'])
        self.assertEqual(review['releaseGate'], 'REJECTED_SOURCE_NOT_PLAYABLE')
        self.assertTrue(review['actualSourcePixelsInspected'])
        self.assertEqual(review['visualReview']['decision'], 'REJECT_AS_GAME_PORTRAIT')
        self.assertFalse(review['gameCropCreated'])
        self.assertFalse(review['fiveStageReviewed'])
        self.assertFalse(review['eligibleForLive'])
        self.assertIsNone(review['gameSha256'])
        self.assertIn(source_key(review['sourcePage']),
                      {source_key(url) for url in person['excludedPhotoSources']})
        source = ROOT / review['sourceImagePath']
        self.assertTrue(source.is_file(), 'Immutable reviewed pixels must remain available')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         review['downloadedSourceSha256'])


if __name__ == '__main__':
    unittest.main()
