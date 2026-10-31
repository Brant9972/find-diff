"""Exact-QID Commons category sitelinks are discovery only, never approval."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import EntityPortraits, SourceError


class FakeHttp:
    def __init__(self, category='Category:Kwong Wa', p373=None, qid='Q5692593'):
        self.category, self.p373, self.qid = category, p373, qid
        self.calls = []

    def json(self, url, **params):
        self.calls.append((url, params))
        if url.startswith('https://zh.wikipedia.org/'):
            return {'query': {'pages': [{'title': '江華',
                'pageprops': {'wikibase_item': self.qid},
                'fullurl': 'https://zh.wikipedia.org/wiki/江華'}]}}
        if params.get('action') == 'wbgetentities':
            assert params['sitefilter'] == 'zhwiki|enwiki|commonswiki'
            claims = {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]}
            if self.p373:
                claims['P373'] = [{'mainsnak': {'datavalue': {'value': self.p373}}}]
            return {'entities': {self.qid: {
                'labels': {'zh': {'value': '江華'}, 'en': {'value': 'Kwong Wa'}},
                'aliases': {}, 'claims': claims,
                'sitelinks': {'commonswiki': {'title': self.category}}}}}
        if params.get('list') == 'categorymembers':
            return {'query': {'categorymembers': [
                {'title': 'File:江華.jpg'}, {'title': 'File:Unsafe.svg'}]}}
        if params.get('titles', '').startswith('File:'):
            return {'query': {'pages': [{'title': 'File:江華.jpg',
                'imageinfo': [{'url': 'https://upload.wikimedia.org/wikipedia/commons/e/e4/江華.jpg',
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:江華.jpg',
                    'extmetadata': {
                        'ImageDescription': {'value': '香港演員江華受訪'},
                        'Artist': {'value': 'am730'},
                        'LicenseShortName': {'value': 'CC BY 3.0'},
                        'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by/3.0/'}}}]}]}}
        if params.get('generator') == 'search':
            return {'query': {'pages': []}}
        raise AssertionError((url, params))


class CommonsSitelinkFallbackTest(unittest.TestCase):
    person = {'name': '江華', 'wikidataId': 'Q5692593',
              'acceptedAnswers': ['江華', 'Kwong Wa']}

    def test_exact_q5_commons_sitelink_finds_file_without_p373(self):
        http = FakeHttp()
        rows = list(EntityPortraits(allow_openverse=False).search(self.person, http))
        categories = [params for _, params in http.calls
                      if params.get('list') == 'categorymembers']
        self.assertEqual(len(categories), 1)
        self.assertEqual(categories[0]['cmtitle'], 'Category:Kwong Wa')
        self.assertLessEqual(categories[0]['cmlimit'], 12)
        self.assertEqual([row['filename'] for row in rows], ['江華.jpg'])
        self.assertEqual(rows[0]['identityEvidence']['wikidataId'], 'Q5692593')
        self.assertEqual(rows[0]['identityEvidence']['commonsCategoryEvidence'],
                         'Wikidata commonswiki sitelink on exact-name Q5 entity')
        self.assertNotIn('eligibleForLive', rows[0])
        self.assertFalse(rows[0]['identityEvidence']['visualIdentityVerified'])
        self.assertNotIn('Unsafe.svg', str(http.calls))

    def test_p373_takes_precedence_over_commons_sitelink(self):
        http = FakeHttp(category='Category:Kwong Wa', p373='Verified Kwong Wa')
        list(EntityPortraits(allow_openverse=False).search(self.person, http))
        categories = [params for _, params in http.calls
                      if params.get('list') == 'categorymembers']
        self.assertEqual(categories[0]['cmtitle'], 'Category:Verified Kwong Wa')

    def test_noncategory_sitelink_cannot_trigger_category_query(self):
        for title in ('File:江華.jpg', 'Category:Unsafe|other', 'Category:Unsafe' + chr(10) + 'Other', ''):
            with self.subTest(title=title):
                http = FakeHttp(category=title)
                list(EntityPortraits(allow_openverse=False).search(self.person, http))
                self.assertFalse(any(p.get('list') == 'categorymembers'
                                     for _, p in http.calls))

    def test_pinned_qid_mismatch_cannot_leak_sitelink(self):
        http = FakeHttp(qid='Q123456')
        with self.assertRaises(SourceError) as ctx:
            list(EntityPortraits(allow_openverse=False).search(self.person, http))
        self.assertEqual(ctx.exception.code, 'identity_unconfirmed')
        self.assertFalse(any(p.get('list') == 'categorymembers'
                             for _, p in http.calls))


if __name__ == '__main__':
    unittest.main()
