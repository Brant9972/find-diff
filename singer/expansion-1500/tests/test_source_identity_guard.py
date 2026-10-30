"""Regression tests for short-name false positives and candidate quotas."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process
from media_pipeline.sources import EntityPortraits, SourceError, identity


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

    def test_relative_only_caption_does_not_identify_pictured_parent(self):
        person = {'name': '黃日華', 'plannedQuestionId': 't1500_0554'}
        class Provider:
            name = 'commons'
            def search(self, person, http, round_number=0):
                for filename, caption in [
                    ('黃芷晴.jpg', '無綫五虎將黃日華的女兒黃芷晴'),
                    ('黃日華.jpg', '黃日華接受專訪'),
                ]:
                    yield {
                        'provider': 'commons',
                        'source': 'https://commons.wikimedia.org/wiki/File:' + filename,
                        'url': 'https://upload.wikimedia.org/' + filename,
                        'filename': filename, 'caption': caption,
                        'license': 'CC BY 4.0',
                        'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                        'artist': 'Fixture photographer',
                        'identityEvidence': {},
                    }
        class HTTP:
            budget = None
            def get(self, url): return b'fixture image bytes'
        def crop(blob):
            return b'fixture cropped jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1],
            }, {'size': [600, 720]}
        row = {'personId': 't1500_0554', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / 'expansion-1500' / 'pipeline'
            process(person, row, root, directory, [Provider()], HTTP(), crop,
                    set(), max_candidates=1, max_attempts=1, active={},
                    rejected_pixels=[])
        ready = [c for c in row['candidates'] if c.get('status') == 'pending_review']
        self.assertEqual([c['filename'] for c in ready], ['黃日華.jpg'])
        self.assertTrue(any(e['code'] == 'identity_context_only'
                            for e in row['lastErrors']))

    def test_huang_yat_wah_plan_excludes_daughter_sources(self):
        import json
        plan = json.loads((Path(__file__).resolve().parents[1] /
                           'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(row for row in plan['selectedNew']
                      if row['plannedQuestionId'] == 't1500_0554')
        self.assertIn('黃芷晴', person['excludedCaptionNames'])
        self.assertEqual(len(person['excludedPhotoSources']), 2)

    def test_pinned_qid_rejects_wrong_same_name_human(self):
        person = {'name': '苗可秀', 'acceptedAnswers': ['苗可秀'],
                  'wikidataId': 'Q702088'}
        class HTTP:
            def json(self, url, **kwargs):
                if 'zh.wikipedia.org' in url:
                    return {'query': {'pages': [{
                        'title': '苗可秀', 'pageprops': {'wikibase_item': 'Q999999'},
                        'fullurl': 'https://zh.wikipedia.org/wiki/苗可秀'}]}}
                if kwargs.get('action') == 'wbgetentities':
                    return {'entities': {'Q999999': {
                        'labels': {'zh': {'value': '苗可秀'},
                                   'en': {'value': 'Other Miao'}},
                        'claims': {'P31': [{
                            'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]}
                    }}}
                raise AssertionError('Unexpected URL: ' + url)
        with self.assertRaises(SourceError) as caught:
            EntityPortraits()._resolve(person, HTTP())
        self.assertEqual(caught.exception.code, 'identity_entity_mismatch')

    def test_nora_miao_military_homonym_is_excluded_before_download(self):
        """An exact Chinese name may refer to a different person (1906 vs 1952)."""
        import json
        plan = json.loads((Path(__file__).resolve().parents[1] /
                           'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(row for row in plan['selectedNew']
                      if row['plannedQuestionId'] == 't1500_0588')
        self.assertEqual(person['wikidataId'], 'Q702088')
        self.assertIn('Nora Miao', person['acceptedAnswers'])
        self.assertTrue(any('File:%E8%8B%97%E5%8F%AF%E7%A7%80.jpg' in source
                            for source in person['excludedPhotoSources']))
        self.assertIn('中國青年黨黨員苗可秀', person['excludedCaptionNames'])

        class Provider:
            name = 'commons'
            def search(self, person, http, round_number=0):
                for source, filename, caption in [
                    ('https://commons.wikimedia.org/wiki/File:%E8%8B%97%E5%8F%AF%E7%A7%80.jpg',
                     '苗可秀.jpg', '中國青年黨黨員苗可秀'),
                    ('https://commons.wikimedia.org/wiki/File:%E8%8B%97%E5%8F%AF%E7%A7%80_1906.jpg',
                     '苗可秀_1906.jpg', '中國青年黨黨員苗可秀'),
                    ('https://commons.wikimedia.org/wiki/File:Nora_Miao_HK.jpg',
                     'Nora_Miao_HK.jpg', 'Nora Miao 香港女演員'),
                ]:
                    yield {'provider': 'commons', 'source': source,
                           'url': 'https://upload.wikimedia.org/' + filename,
                           'filename': filename, 'caption': caption,
                           'license': 'CC BY 4.0',
                           'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                           'artist': 'Fixture photographer',
                           'identityEvidence': {'wikidataId': 'Q702088'}}

        class HTTP:
            budget = None
            def __init__(self):
                self.downloaded = []
            def get(self, url):
                self.downloaded.append(url)
                return b'fixture image bytes'

        def crop(blob):
            return b'fixture cropped jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1]}, {'size': [600, 720]}

        row = {'personId': 't1500_0588', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process(person, row, root, root / 'expansion-1500' / 'pipeline',
                    [Provider()], http, crop, set(), max_candidates=1,
                    max_attempts=1, active={}, rejected_pixels=[])
        ready = [c for c in row['candidates'] if c.get('status') == 'pending_review']
        self.assertEqual([c['filename'] for c in ready], ['Nora_Miao_HK.jpg'])
        self.assertEqual(len(http.downloaded), 1)
        self.assertIn('Nora_Miao_HK.jpg', http.downloaded[0])
        self.assertTrue(any(e['code'] == 'review_identity_conflict'
                            for e in row['lastErrors']))

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
