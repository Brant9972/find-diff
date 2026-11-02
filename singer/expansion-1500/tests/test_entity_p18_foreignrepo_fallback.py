"""Pinned Q5 Wikidata P18 foreign-repository recovery is metadata only."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import EntityPortraits, SourceError, identity_key, rights

FILE = 'TestSinger.jpg'
COMMONS_PAGE = 'https://commons.wikimedia.org/wiki/File:' + FILE
UPLOAD = 'https://upload.wikimedia.org/wikipedia/commons/a/ab/' + FILE
PERSON = {'name': '測試歌手', 'acceptedAnswers': ['測試歌手'],
          'wikidataId': 'Q1234567'}


def page(title='File:' + FILE, source=COMMONS_PAGE, url=UPLOAD):
    return {'title': title, 'imageinfo': [{
        'url': url, 'descriptionurl': source,
        'width': 1800, 'height': 2200,
        'extmetadata': {key: {'value': value} for key, value in {
            'Artist': 'Test Photographer',
            'LicenseShortName': 'CC BY-SA 4.0',
            'LicenseUrl': 'https://creativecommons.org/licenses/by-sa/4.0/',
            'ImageDescription': '測試歌手的單人肖像',
        }.items()},
    }]}


class FakeHTTP:
    def __init__(self, commons='refused', foreign=None, foreign_error=False):
        self.commons = commons
        self.foreign = page() if foreign is None else foreign
        self.foreign_error = foreign_error
        self.calls = []
        self.verified_identities = {
            identity_key(PERSON): {
                'aliases': ['測試歌手'], 'englishAliases': [],
                'query': '測試歌手',
                'evidence': {'wikidataId': 'Q1234567',
                             'visualIdentityVerified': False},
                'files': [FILE],
            }
        }

    def json(self, url, **params):
        self.calls.append((url, params))
        if params.get('generator') == 'search':
            return {'query': {'pages': []}}
        if params.get('titles') == 'File:' + FILE:
            if url.startswith('https://commons.wikimedia.org/'):
                if self.commons == 'refused':
                    raise SourceError('http_403', 'Commons metadata refused')
                if self.commons == 'empty':
                    return {'query': {'pages': [{'title': 'File:' + FILE,
                                                'missing': True}]}}
                return {'query': {'pages': [page()]}}
            if url.startswith('https://en.wikipedia.org/'):
                if self.foreign_error:
                    raise SourceError('http_429', 'Foreign repo rate limited')
                return {'query': {'pages': [self.foreign]}}
        raise AssertionError((url, params))


class P18ForeignRepoFallbackTest(unittest.TestCase):
    def candidates(self, http):
        return list(EntityPortraits(allow_openverse=False).search(PERSON, http))

    def test_refused_commons_p18_recovers_only_exact_shared_file_metadata(self):
        http = FakeHTTP()
        rows = self.candidates(http)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['source'], COMMONS_PAGE)
        self.assertEqual(rows[0]['identityEvidence']['claim'], 'P18')
        self.assertTrue(rows[0]['identityEvidence']['foreignRepoFallback'])
        self.assertFalse(rows[0]['identityEvidence']['visualIdentityVerified'])
        self.assertFalse(rows[0].get('eligibleForLive', False))
        self.assertEqual(rights(rows[0]), 'open_license_metadata')
        foreign = [(u, p) for u, p in http.calls if 'en.wikipedia.org' in u]
        self.assertEqual(len(foreign), 1)
        self.assertEqual(foreign[0][1]['titles'], 'File:' + FILE)
        self.assertNotIn('generator', foreign[0][1])

    def test_empty_commons_p18_uses_single_bounded_fallback(self):
        http = FakeHTTP(commons='empty')
        self.assertEqual(len(self.candidates(http)), 1)
        self.assertEqual(sum('en.wikipedia.org' in u for u, _ in http.calls), 1)

    def test_healthy_commons_p18_does_not_query_foreign_repo(self):
        http = FakeHTTP(commons='healthy')
        rows = self.candidates(http)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['identityEvidence'].get('foreignRepoFallback'))
        self.assertFalse(any('en.wikipedia.org' in u for u, _ in http.calls))

    def test_foreign_local_wikipedia_upload_cannot_inherit_qid(self):
        http = FakeHTTP(foreign=page(
            source='https://en.wikipedia.org/wiki/File:' + FILE,
            url='https://upload.wikimedia.org/wikipedia/en/a/ab/' + FILE))
        with self.assertRaises(SourceError):
            self.candidates(http)

    def test_foreign_different_commons_file_is_rejected(self):
        http = FakeHTTP(foreign=page(
            source='https://commons.wikimedia.org/wiki/File:OtherPerson.jpg'))
        with self.assertRaises(SourceError):
            self.candidates(http)

    def test_foreign_different_title_is_rejected(self):
        http = FakeHTTP(foreign=page(title='File:OtherPerson.jpg'))
        with self.assertRaises(SourceError):
            self.candidates(http)

    def test_foreign_non_commons_original_is_rejected(self):
        http = FakeHTTP(foreign=page(
            url='https://upload.wikimedia.org/wikipedia/en/a/ab/' + FILE))
        with self.assertRaises(SourceError):
            self.candidates(http)

    def test_foreign_api_failure_does_not_promote_any_candidate(self):
        http = FakeHTTP(foreign_error=True)
        with self.assertRaises(SourceError):
            self.candidates(http)
        self.assertEqual(sum('en.wikipedia.org' in u for u, _ in http.calls), 1)


if __name__ == '__main__':
    unittest.main()
