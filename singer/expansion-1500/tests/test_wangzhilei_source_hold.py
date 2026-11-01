"""Wang Zhilei exact Commons hint is a source lead, never live approval."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import identity, rights


class WangZhileiSourceHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        cls.person, = [p for p in plan['selectedNew']
                       if p['plannedQuestionId'] == 't1500_0381']
        cls.review = json.loads((ROOT / 'pipeline/chatgpt-review/'
                                 '20261101-wangzhilei-exact-commons-source-lead.json')
                                .read_text(encoding='utf-8'))

    def test_exact_file_is_only_a_discovery_hint(self):
        self.assertEqual(self.person['name'], '王芷蕾')
        self.assertEqual(self.person['reviewExactCommonsFiles'], ['Jeanette Wang.JPG'])
        self.assertEqual(self.person['aliases'], ['Jeanette Wang'])
        self.assertEqual(self.person['acceptedAnswers'], ['王芷蕾', 'Jeanette Wang'])
        self.assertEqual(self.person['cachedMetadataRecheckToken'],
                         '20261101-wangzhilei-english-caption-q9066613')
        self.assertNotEqual(self.person['photoStatus'], 'published')
        self.assertEqual(self.person['qaStatus'], 'not_releasable')

    def test_exact_english_filename_matches_verified_alias(self):
        self.assertIn('Jeanette Wang', identity(self.person, 'Jeanette Wang.JPG'))
        self.assertNotIn('Jeanette Wang', identity(self.person, 'Cher Wang at WEF.jpg'))

    def test_rights_not_automatically_promoted(self):
        p = self.review['person']
        self.assertEqual(self.review['releaseGate'], 'SOURCE_ONLY_NOT_PLAYABLE')
        self.assertEqual(p['canonicalWikidataQid'], 'Q9066613')
        self.assertEqual(p['originalSha1'],
                         'bb8bbe3a75986502d726064bb228654c81a78e26')
        self.assertFalse(p['rightsIndependentlyVerified'])
        self.assertFalse(p['eligibleForLive'])
        self.assertEqual(rights({'license': p['commonsRightsLabel'],
                                 'licenseUrl': p['licenseUrl'],
                                 'artist': p['author']}), 'needs_review')

    def test_no_game_crop_or_five_stage_approval(self):
        p = self.review['person']
        self.assertTrue(p['visualSourceOnly']['thumbnailInspected'])
        self.assertFalse(p['visualSourceOnly']['gameCropInspected'])
        self.assertFalse(p['visualSourceOnly']['fiveStageInspected'])
        self.assertFalse(p['identityIndependentlyVerified'])


if __name__ == '__main__':
    unittest.main()
