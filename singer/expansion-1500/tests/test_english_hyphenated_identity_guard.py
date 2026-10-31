"""Prevent romanized-name suffix matches from misidentifying performers."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import identity, source_key


class HyphenatedEnglishNameGuardTest(unittest.TestCase):
    def setUp(self):
        self.person = {
            'name': '林煒', 'aliases': ['Wei Lin'],
            'acceptedAnswers': ['林煒'],
        }

    def test_baseball_player_tzu_wei_lin_is_not_actor_wei_lin(self):
        self.assertEqual(identity(self.person,
            'Tzu-Wei Lin in 2017 (36962867110).jpg'), [])
        self.assertEqual(identity(self.person,
            'Tzu-Wei Lin in 2017 (36962867110) (cropped).jpg'), [])
        self.assertEqual(identity(self.person,
            'John-Wei Lin 2024.jpg'), [])

    def test_standalone_actor_romanized_name_still_matches(self):
        self.assertIn('Wei Lin', identity(self.person, 'Wei Lin portrait.jpg'))
        self.assertIn('Wei Lin', identity(self.person, '2017 Wei Lin at film event'))
        self.assertIn('林煒', identity(self.person, '演員林煒訪談'))

    def test_wrong_person_exact_source_is_excluded_without_removing_actor(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        row = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0433')
        self.assertEqual(row['wikidataId'], 'Q580322')
        rejected = {source_key(x) for x in row['excludedPhotoSources']}
        self.assertIn(source_key('https://commons.wikimedia.org/wiki/File:Tzu-Wei_Lin_in_2017_(36962867110).jpg'), rejected)
        self.assertNotEqual(row['photoStatus'], 'published')
        self.assertFalse(row['imageVerification']['finalCropReviewed'])


if __name__ == '__main__':
    unittest.main()
