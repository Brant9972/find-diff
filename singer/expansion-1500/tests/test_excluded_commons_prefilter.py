"""Rejected Commons file pages must not consume source API calls or retries."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import CommonsSearch, CuratedCommons, EntityPortraits, Wikimedia, excluded_commons_keys


class FakeCommons:
    def __init__(self):
        self.calls = []
        self.urls = []

    def json(self, url, **params):
        self.calls.append(params)
        self.urls.append(url)
        if params.get('titles'):
            return {'query': {'pages': []}}
        return {'query': {'pages': [
            {'title': 'File:王耀慶@2011.jpg',
             'imageinfo': [{
                 'descriptionurl': 'https://commons.wikimedia.org/wiki/File:%E7%8E%8B%E8%80%80%E6%85%B6%402011.jpg',
                 'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ac/ignored.jpg',
                 'width': 1014, 'height': 1386,
                 'extmetadata': {}}]},
            {'title': 'File:New_Wang_Portrait.jpg',
             'imageinfo': [{
                 'descriptionurl': 'https://commons.wikimedia.org/wiki/File:New_Wang_Portrait.jpg',
                 'url': 'https://upload.wikimedia.org/wikipedia/commons/1/11/new.jpg',
                 'width': 1600, 'height': 2000,
                 'extmetadata': {}}]},
        ]}}


class RejectedSourcePreFilterTest(unittest.TestCase):
    def setUp(self):
        self.person = {
            'name': '王耀慶',
            'reviewExactCommonsFiles': ['王耀慶@2011.jpg', 'New Wang Portrait.jpg'],
            'excludedPhotoSources': [
                'https://commons.wikimedia.org/wiki/File:王耀慶@2011.jpg'],
        }

    def test_rejected_exact_file_never_reaches_imageinfo(self):
        api = FakeCommons()
        with patch('media_pipeline.sources.verified_identity', return_value=None):
            rows = list(CommonsSearch().search(self.person, api))
        exact = [p['titles'] for url, p in zip(api.urls, api.calls)
                 if p.get('titles') and 'commons.wikimedia.org' in url]
        self.assertEqual(exact, ['File:New Wang Portrait.jpg'])
        foreign = [p['titles'] for url, p in zip(api.urls, api.calls)
                   if p.get('titles') and 'en.wikipedia.org' in url]
        self.assertEqual(foreign, ['File:New Wang Portrait.jpg'])
        self.assertEqual([r['filename'] for r in rows],
                         ['New_Wang_Portrait.jpg'])
        self.assertEqual(len(excluded_commons_keys(self.person)), 1)

    def test_all_excluded_still_allows_new_source_search(self):
        api = FakeCommons()
        person = {**self.person, 'reviewExactCommonsFiles': ['王耀慶@2011.jpg']}
        with patch('media_pipeline.sources.verified_identity', return_value=None):
            rows = list(CommonsSearch().search(person, api))
        self.assertFalse(any('titles' in p for p in api.calls))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['filename'], 'New_Wang_Portrait.jpg')

    def test_entity_p18_skips_rejected_source_before_imageinfo(self):
        api = FakeCommons()
        with patch.object(EntityPortraits, '_resolve', return_value=(
                ['王耀慶'], '王耀慶', {'wikidataId': 'Q9315976'},
                ['王耀慶@2011.jpg', 'New Wang Portrait.jpg'])):
            rows = list(EntityPortraits(allow_openverse=False).search(
                self.person, api))
        commons_exact = [p['titles'] for url, p in zip(api.urls, api.calls)
                         if p.get('titles') and 'commons.wikimedia.org' in url]
        foreign_exact = [p['titles'] for url, p in zip(api.urls, api.calls)
                         if p.get('titles') and 'en.wikipedia.org' in url]
        # An empty Commons P18 response now permits one *exact same title*
        # shared-repository lookup, never the previously rejected file.
        self.assertEqual(commons_exact, ['File:New Wang Portrait.jpg'])
        self.assertEqual(foreign_exact, ['File:New Wang Portrait.jpg'])
        self.assertEqual([r['filename'] for r in rows],
                         ['New_Wang_Portrait.jpg'])

    def test_curated_original_respects_exact_rejection(self):
        person = {
            'name': '葛民輝', 'aliases': ['Eric Kot'],
            'reviewExactCommonsFiles': ['Eric Kot 20231029.jpg'],
            'excludedPhotoSources': [
                'https://commons.wikimedia.org/wiki/File:Eric_Kot_20231029.jpg'],
            'reviewVerifiedOriginalSources': [{
                'filename': 'Eric Kot 20231029.jpg',
                'source': 'https://commons.wikimedia.org/wiki/File:Eric_Kot_20231029.jpg',
                'url': 'https://upload.wikimedia.org/wikipedia/commons/6/63/Eric_Kot_20231029.jpg',
                'artist': 'Tombus20032000', 'caption': '葛民輝 at event',
                'license': 'CC BY-SA 4.0',
                'licenseUrl': 'https://creativecommons.org/licenses/by-sa/4.0/',
                'sourceType': 'uploader_own_work',
                'verificationUrl': 'https://commons.wikimedia.org/wiki/File:Eric_Kot_20231029.jpg',
                'verifiedAt': '2026-10-30',
            }],
        }
        self.assertEqual(list(CuratedCommons().search(person, None)), [])
        person['excludedPhotoSources'] = []
        self.assertEqual(len(list(CuratedCommons().search(person, None))), 1)




class LegacyWikimediaExcludedFileTest(unittest.TestCase):
    def test_article_p18_and_search_cannot_reintroduce_rejected_file(self):
        """All three legacy discovery paths share the exact-source rejection."""
        rejected = '王耀慶@2011.jpg'
        fresh = 'New Wang Portrait.jpg'

        class FakeLegacyAPI:
            def __init__(self):
                self.calls = []

            def json(self, url, **params):
                self.calls.append((url, params))
                if 'zh.wikipedia.org' in url:
                    return {'query': {'pages': [{
                        'title': '王耀慶',
                        'extract': '台灣演員王耀慶接受專訪。',
                        'pageprops': {'wikibase_item': 'Q9315976'},
                        'pageimage': rejected,
                        'images': [{'title': 'File:' + fresh}],
                    }]}}
                if 'en.wikipedia.org' in url:
                    return {'query': {'pages': []}}
                if 'wikidata.org' in url:
                    return {'entities': {'Q9315976': {'claims': {'P18': [
                        {'mainsnak': {'datavalue': {'value': rejected}}},
                        {'mainsnak': {'datavalue': {'value': fresh}}},
                    ]}}}}
                if params.get('generator') == 'search':
                    return {'query': {'pages': [
                        {'title': 'File:' + rejected},
                        {'title': 'File:' + fresh},
                    ]}}
                if params.get('titles') == 'File:' + fresh:
                    return {'query': {'pages': [{
                        'imageinfo': [{
                            'url': 'https://upload.wikimedia.org/wikipedia/commons/1/11/new.jpg',
                            'descriptionurl': 'https://commons.wikimedia.org/wiki/File:New_Wang_Portrait.jpg',
                            'extmetadata': {},
                        }],
                    }]}}
                raise AssertionError('Rejected or unexpected imageinfo request: ' +
                                     str((url, params)))

        person = {
            'name': '王耀慶',
            'wikidataId': 'Q9315976',
            'excludedPhotoSources': [
                'https://commons.wikimedia.org/wiki/File:%E7%8E%8B%E8%80%80%E6%85%B6%402011.jpg',
            ],
        }
        api = FakeLegacyAPI()
        rows = list(Wikimedia().search(person, api))
        self.assertEqual([row['filename'] for row in rows], [fresh])
        self.assertEqual(
            [params['titles'] for _, params in api.calls if 'titles' in params
             and 'commons.wikimedia.org' in _],
            ['File:' + fresh],
        )
        self.assertTrue(any(params.get('generator') == 'search'
                            for _, params in api.calls))

if __name__ == '__main__':
    unittest.main()
