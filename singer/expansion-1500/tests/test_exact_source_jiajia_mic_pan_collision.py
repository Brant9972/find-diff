"""Exact Commons rejections are image-scoped, not person-scoped."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import excluded_commons_keys, source_key


class ExactSourceVisualAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        cls.people = {p['plannedQuestionId']: p for p in plan['selectedNew']}

    def test_mic_obstructed_jiajia_source_excluded_but_singer_remains(self):
        person = self.people['t1500_0390']
        self.assertEqual(person['name'], '家家')
        self.assertIn('紀家盈', person['acceptedAnswers'])
        source = 'https://commons.wikimedia.org/wiki/File:JiJiaJia_20121230.JPG'
        self.assertIn(source, person['excludedPhotoSources'])
        self.assertIn(source_key(source), excluded_commons_keys(person))
        self.assertEqual(source_key(source),
                         source_key('https://commons.wikimedia.org/wiki/File:JiJiaJia%20201230.JPG'))
        self.assertNotEqual(person.get('photoStatus'), 'published')

    def test_michelle_pan_is_other_singer_not_pan_meichen(self):
        person = self.people['t1500_0156']
        self.assertEqual(person['name'], '潘美辰')
        source = 'https://commons.wikimedia.org/wiki/File:Michelle_Pan_20101127.jpg'
        self.assertIn(source, person['excludedPhotoSources'])
        self.assertIn(source_key(source), excluded_commons_keys(person))
        self.assertNotIn('潘越雲', person['acceptedAnswers'])
        self.assertNotEqual(person.get('photoStatus'), 'published')

    def test_wang_zhilei_has_concrete_record_label_verified_hints(self):
        person = self.people['t1500_0381']
        self.assertEqual(person['name'], '王芷蕾')
        self.assertEqual(person['representativeWorks'], ['台北的天空', '翩翩飛起'])
        self.assertEqual({x['title'] for x in person['verifiedWorkSources']},
                         {'台北的天空', '翩翩飛起'})
        self.assertTrue(any('warnermusic.com.tw' in x['url']
                            for x in person['verifiedWorkSources']))
        self.assertTrue(any('music-tw.line.me' in x['url']
                            for x in person['verifiedWorkSources']))
        self.assertNotEqual(person.get('qaStatus'), 'released')

    def test_exclusions_do_not_blacklist_people_or_unrelated_sources(self):
        for pid in ('t1500_0390', 't1500_0156'):
            person = self.people[pid]
            self.assertEqual(len(person['excludedPhotoSources']), 1)
            self.assertNotIn(source_key('https://commons.wikimedia.org/wiki/File:Another_Portrait.jpg'),
                             excluded_commons_keys(person))


if __name__ == '__main__':
    unittest.main()
