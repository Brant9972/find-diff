"""Bounded foreign-repo imageinfo fallback: metadata discovery, never approval."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import CommonsSearch, SourceError, rights


FILE = 'Jeanette_Wang.JPG'
COMMONS_PAGE = 'https://commons.wikimedia.org/wiki/File:' + FILE


def file_page(source=COMMONS_PAGE, title='File:' + FILE):
    return {'title': title, 'imageinfo': [{
        'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/' + FILE,
        'descriptionurl': source, 'width': 2048, 'height': 1536,
        'extmetadata': {key: {'value': value} for key, value in {
            'Artist': '竹筍弟弟',
            'LicenseShortName': 'CC BY-SA 3.0',
            'LicenseUrl': 'https://creativecommons.org/licenses/by-sa/3.0/',
            'ImageDescription': '臺灣歌手王芷蕾於臺灣電視公司前留影',
        }.items()}
    }]}


class ExactForeignRepoAPI:
    def __init__(self, commons='error', foreign=None):
        self.commons = commons
        self.foreign = foreign if foreign is not None else file_page()
        self.calls = []

    def json(self, url, **params):
        self.calls.append((url, params))
        if params.get('titles') == 'File:' + FILE:
            if 'commons.wikimedia.org' in url:
                if self.commons == 'error':
                    raise SourceError('http_403', 'Commons exact lookup refused')
                if self.commons == 'empty':
                    return {'query': {'pages': [{'title': 'File:' + FILE, 'missing': True}]}}
                return {'query': {'pages': [file_page()]}}
            if 'en.wikipedia.org' in url:
                return {'query': {'pages': [self.foreign]}}
        if params.get('generator') == 'search':
            return {'query': {'pages': []}}
        if params.get('list') == 'allimages':
            return {'query': {'allimages': []}}
        raise AssertionError('Unexpected request: ' + url + ' ' + str(params))


class ExactForeignRepoFallbackTest(unittest.TestCase):
    person = {'name': '王芷蕾', 'reviewExactCommonsFiles': [FILE]}

    def test_commons_refusal_recovers_exact_shared_file_metadata(self):
        api = ExactForeignRepoAPI()
        rows = list(CommonsSearch().search(self.person, api))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source'], COMMONS_PAGE)
        self.assertEqual(rows[0]['filename'], FILE)
        self.assertEqual(rights(rows[0]), 'open_license_metadata')
        self.assertTrue(rows[0]['identityEvidence']['curatedExactFileHint'])
        self.assertFalse(rows[0]['identityEvidence'].get('visualIdentityVerified', False))
        foreign = [(url, p) for url, p in api.calls if 'en.wikipedia.org' in url]
        self.assertEqual(len(foreign), 1)
        self.assertEqual(foreign[0][1]['titles'], 'File:' + FILE)
        self.assertNotIn('generator', foreign[0][1])
        self.assertNotIn('gsrsearch', foreign[0][1])

    def test_empty_commons_imageinfo_uses_one_bounded_fallback(self):
        api = ExactForeignRepoAPI(commons='empty')
        rows = list(CommonsSearch().search(self.person, api))
        self.assertEqual(len(rows), 1)
        self.assertEqual(sum('en.wikipedia.org' in url for url, _ in api.calls), 1)

    def test_healthy_commons_exact_does_not_call_foreign_repo(self):
        api = ExactForeignRepoAPI(commons='success')
        self.assertEqual(len(list(CommonsSearch().search(self.person, api))), 1)
        self.assertFalse(any('en.wikipedia.org' in url for url, _ in api.calls))

    def test_local_wikipedia_file_cannot_masquerade_as_commons(self):
        api = ExactForeignRepoAPI(foreign=file_page(
            source='https://en.wikipedia.org/wiki/File:' + FILE))
        with self.assertRaises(SourceError):
            list(CommonsSearch().search(self.person, api))
        self.assertFalse(any('en.wikipedia.org' in url and p.get('generator')
                             for url, p in api.calls))

    def test_different_commons_file_cannot_replace_curated_title(self):
        api = ExactForeignRepoAPI(foreign=file_page(
            source='https://commons.wikimedia.org/wiki/File:Another_Person.jpg'))
        with self.assertRaises(SourceError):
            list(CommonsSearch().search(self.person, api))

    def test_different_foreign_page_title_is_rejected(self):
        api = ExactForeignRepoAPI(foreign=file_page(
            title='File:Different_Person.jpg'))
        with self.assertRaises(SourceError):
            list(CommonsSearch().search(self.person, api))


if __name__ == '__main__':
    unittest.main()
