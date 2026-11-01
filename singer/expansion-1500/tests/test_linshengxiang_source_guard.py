"""Lin Sheng-xiang Commons category membership is not image identity approval."""
import json
import unittest
from pathlib import Path
from urllib.parse import quote

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import source_key, excluded_commons_keys

ROOT = Path(__file__).resolve().parents[1]
FILE = (
    '學者管中祥與歌手林生祥參加20120901反媒體壟斷大遊行 '
    'Scholar and Singer join Protest against anti-Democracy media-monopoly in TAIWAN.jpg'
)


class LinShengXiangSourceGuardTest(unittest.TestCase):
    def test_cluttered_exact_source_is_excluded_and_person_remains_eligible(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0106')
        self.assertEqual(person['name'], '林生祥')
        self.assertEqual(person['wikidataId'], 'Q8986967')
        self.assertNotIn(FILE, person['reviewExactCommonsFiles'])
        source = 'https://commons.wikimedia.org/wiki/File:' + quote(FILE.replace(' ', '_'))
        self.assertIn(source_key(source), excluded_commons_keys(person))
        self.assertIn('2026-11-02 additional source-only visual screening', person['reviewReason'])
        self.assertIn('CC BY-SA 2.0', person['reviewReason'])
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        self.assertFalse(person['imageVerification']['rightsDocumented'])
        self.assertNotEqual(person['photoStatus'], 'published')
        self.assertEqual(person['qaStatus'], 'not_releasable')

    def test_category_membership_and_low_resolution_are_not_validated_as_portraits(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0106')
        excluded = set(person['excludedPhotoSources'])
        for filename in (
            '林生祥獲第54屆金馬原創音樂雙料獎.jpg',
            '五月二十日_中華民國第十四任總統、副總統就職慶祝典禮_(26521078403).jpg',
        ):
            with self.subTest(filename=filename):
                self.assertIn('https://commons.wikimedia.org/wiki/File:' + filename, excluded)
        self.assertIn('Panai', person['reviewReason'])
        self.assertNotIn('林生祥獲第54屆金馬原創音樂雙料獎.jpg',
                         person['reviewExactCommonsFiles'])


if __name__ == '__main__':
    unittest.main()
