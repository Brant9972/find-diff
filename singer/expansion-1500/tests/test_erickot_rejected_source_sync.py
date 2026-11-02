"""Keep the actor eligible while rejecting only pixel-verified unusable sources."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import CuratedCommons, excluded_commons_keys, source_key


class EricKotSourceExclusionTest(unittest.TestCase):
    def test_rejected_portraits_not_requeued_as_curated_sources(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(p for p in plan['selectedNew']
                      if p['plannedQuestionId'] == 't1500_0564')
        self.assertEqual(person['name'], '葛民輝')
        self.assertEqual(person['wikidataId'], 'Q590914')
        self.assertNotEqual(person['photoStatus'], 'published')
        rejected = {
            'https://commons.wikimedia.org/wiki/File:Eric_Kot_200812.JPG',
            'https://commons.wikimedia.org/wiki/File:Eric_Kot_20231029.jpg',
            'https://commons.wikimedia.org/wiki/File:EricKot2007.jpg',
        }
        self.assertTrue(rejected.issubset(set(person['excludedPhotoSources'])))
        self.assertTrue(all(source_key(url) in excluded_commons_keys(person)
                            for url in rejected))
        self.assertEqual(list(CuratedCommons().search(person, None)), [])
        self.assertIn('582x703', person['reviewReason'])
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        # These are exact photo exclusions, not a ban on searching for the actor.
        self.assertIn('t1500_0564', {p['plannedQuestionId']
                                    for p in plan['selectedNew']})


if __name__ == '__main__':
    unittest.main()
