"""Regression tests for short-name false positives and candidate quotas."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process
from media_pipeline.sources import identity


class IdentityGuardTest(unittest.TestCase):
    def test_short_chinese_names_do_not_match_longer_names_or_businesses(self):
        self.assertEqual(identity({'name': '家家'}, '香港家家美食餐廳'), [])
        self.assertEqual(identity({'name': '黃玠'}, '黃玠瑋 Zooey Wonder'), [])
        self.assertEqual(identity({'name': '家家'}, '歌手家家 2024 演出'), ['家家'])
        self.assertEqual(identity({'name': '黃玠'}, '黃玠 portrait 2024'), ['黃玠'])

    def test_romanised_name_needs_a_whole_name(self):
        self.assertEqual(identity({'name': 'Ben Wong'}, 'Ben Wongster portrait'), [])
        self.assertEqual(identity({'name': 'Ben Wong'}, 'Ben-Wong portrait'), ['Ben Wong'])

    def test_three_pixel_rejected_sources_are_excluded_from_release_plan(self):
        import json
        plan = json.loads((Path(__file__).resolve().parents[1] /
                           'release-plan-20261028.json').read_text(encoding='utf-8'))
        people = {row['plannedQuestionId']: row for row in plan['selectedNew']}
        expected = {
            't1500_0561': '2010_Hong_Kong_International_Film_Festival_',
            't1500_0571': 'China_Guardian_Autumn_Auction_',
            't1500_0587': '%E5%BB%96%E5%95%9F%E6%99%BA2019.jpg',
        }
        for person_id, filename_fragment in expected.items():
            with self.subTest(person_id=person_id):
                sources = people[person_id].get('excludedPhotoSources', [])
                self.assertTrue(any(filename_fragment in source for source in sources))
                self.assertTrue(all(source.startswith('https://commons.wikimedia.org/wiki/File:')
                                    for source in sources))

    def test_wrong_search_result_does_not_consume_image_quota(self):
        person = {'name': '家家', 'plannedQuestionId': 't1'}
        class Provider:
            name = 'commons'
            def search(self, person, http, round_number=0):
                for suffix, caption in [('restaurant', '香港家家美食餐廳'),
                                        ('portrait', '家家 2024 portrait')]:
                    yield {'provider': 'commons', 'source': 'https://commons.wikimedia.org/wiki/File:' + suffix,
                           'url': 'https://upload.wikimedia.org/' + suffix + '.jpg',
                           'filename': suffix + '.jpg', 'caption': caption,
                           'license': 'CC BY 4.0', 'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                           'artist': 'Fixture photographer',
                           'identityEvidence': {'matchedAliases': ['家家']}}
        class HTTP:
            budget = None
            def get(self, url):
                return b'fixture image bytes'
        def crop(blob):
            return b'fixture cropped jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1]}, {'size': [600, 720]}
        row = {'personId': 't1', 'status': 'not_started', 'attempts': 0,
               'candidates': [], 'history': []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / 'expansion-1500' / 'pipeline'
            process(person, row, root, directory, [Provider()], HTTP(), crop,
                    set(), max_candidates=1, max_attempts=1, active={}, rejected_pixels=[])
        ready = [c for c in row['candidates'] if c.get('status') == 'pending_review']
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]['filename'], 'portrait.jpg')
        self.assertTrue(any(e['code'] == 'identity_unconfirmed' for e in row['lastErrors']))


if __name__ == '__main__':
    unittest.main()
