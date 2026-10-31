"""Rejected Commons file pages must not consume source API calls or retries."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import CommonsSearch, CuratedCommons, excluded_commons_keys


class FakeCommons:
    def __init__(self):
        self.calls = []

    def json(self, url, **params):
        self.calls.append(params)
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
        exact = [p['titles'] for p in api.calls if p.get('titles')]
        self.assertEqual(exact, ['File:New Wang Portrait.jpg'])
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


if __name__ == '__main__':
    unittest.main()
