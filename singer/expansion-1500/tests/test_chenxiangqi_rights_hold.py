"""Keep the Chen Shiang-chyi pixel review draft-only until source rights are verified."""
import json
import unittest
from pathlib import Path


class ChenShiangChyiReviewTest(unittest.TestCase):
    def test_rights_hold_and_immutable_visual_evidence(self):
        root = Path(__file__).resolve().parents[1]
        path = root / 'pipeline/chatgpt-review/20261031-chen-shiang-chyi-visual-rights-pending.json'
        review = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(review['releaseGate'], 'DRAFT_ONLY_NOT_PLAYABLE')
        self.assertEqual(review['summary']['approvedForLive'], 0)
        self.assertEqual(review['sourceAssetCommit'],
                         'c05e16f2805ad23290b429ccf0a430bbf7d7b1ff')
        decision, = review['decisions']
        self.assertEqual(decision['personId'], 't1500_0171')
        self.assertEqual(decision['candidateId'],
                         'manualrecrop-f186fd95e6ed-4bcc5ace')
        self.assertEqual(decision['gameSha256'],
                         'f186fd95e6ed3d7592fd3a0ceba6f51d74f5fb04e455f7c4ba47a88a24562fb4')
        self.assertFalse(decision['eligibleForLive'])
        self.assertFalse(decision['rightsEvidence']['youtubeLicenseIndependentlyReverified'])
        self.assertFalse(decision['rightsEvidence']['commonsLicenseReviewerIdentified'])
        self.assertFalse(decision['identityEvidence']['independentFaceIdentityConfirmed'])
        self.assertEqual(set(decision['fiveStageVisual']),
                         {'eyes', 'nose', 'mouth', 'chin', 'full'})
        self.assertEqual(decision['cropDimensions'], [600, 720])


if __name__ == '__main__':
    unittest.main()
