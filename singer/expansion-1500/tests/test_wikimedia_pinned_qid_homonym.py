"""A homonymous Wikipedia article must not override a curator-pinned QID."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import Wikimedia


class FakeAPI:
    def __init__(self, article_qid):
        self.article_qid = article_qid
        self.calls = []

    def json(self, url, **params):
        self.calls.append((url, params))
        if 'zh.wikipedia.org' in url:
            return {'query': {'pages': [{
                'title': '苗可秀', 'extract': '演員苗可秀參與電影拍攝。',
                'pageprops': {'wikibase_item': self.article_qid},
                'pageimage': 'ArticlePortrait.jpg',
                'images': [{'title': 'File:ArticlePortrait.jpg'}],
                'fullurl': 'https://zh.wikipedia.org/wiki/苗可秀',
            }]}}
        if 'en.wikipedia.org' in url:
            return {'query': {'pages': []}}
        if 'wikidata.org' in url:
            return {'entities': {self.article_qid: {'claims': {
                'P18': [{'mainsnak': {'datavalue': {'value': 'ArticlePortrait.jpg'}}}],
            }}}}
        if 'commons.wikimedia.org' in url:
            if params.get('generator') == 'search':
                return {'query': {'pages': []}}
            if params.get('titles') == 'File:ArticlePortrait.jpg':
                return {'query': {'pages': [{
                    'title': 'File:ArticlePortrait.jpg',
                    'imageinfo': [{
                        'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/ArticlePortrait.jpg',
                        'descriptionurl': 'https://commons.wikimedia.org/wiki/File:ArticlePortrait.jpg',
                        'extmetadata': {
                            'Artist': {'value': 'Fixture photographer'},
                            'ImageDescription': {'value': '苗可秀 portrait'},
                            'LicenseShortName': {'value': 'CC BY 4.0'},
                            'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by/4.0/'},
                        },
                    }],
                }]}}
        raise AssertionError(f'Unexpected request: {url} {params}')


class PinnedQidHomonymTest(unittest.TestCase):
    def test_different_qid_discards_article_and_p18_without_blocking_commons_search(self):
        api = FakeAPI('Q7654321')
        person = {'name': '苗可秀', 'wikidataId': 'Q1234567'}
        results = list(Wikimedia().search(person, api))
        self.assertEqual(results, [])
        self.assertFalse(any('wikidata.org' in url for url, _ in api.calls))
        self.assertFalse(any(params.get('titles') == 'File:ArticlePortrait.jpg'
                             for _, params in api.calls))
        self.assertTrue(any(params.get('generator') == 'search'
                            for _, params in api.calls))

    def test_matching_qid_preserves_article_p18_as_unapproved_candidate(self):
        api = FakeAPI('Q1234567')
        person = {'name': '苗可秀', 'wikidataId': 'Q1234567'}
        results = list(Wikimedia().search(person, api))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['identityEvidence']['wikidataId'], 'Q1234567')
        self.assertEqual(results[0]['filename'], 'ArticlePortrait.jpg')
        # A source lead is never a human-approved game portrait.
        self.assertFalse(results[0].get('eligibleForLive', False))


if __name__ == '__main__':
    unittest.main()
