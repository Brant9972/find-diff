"""Regression coverage for bounded Commons zero-result source discovery.

An empty CirrusSearch response is not a negative portrait verdict. Filename
prefix fallback is strictly bounded, metadata-only and cannot release photos.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import CommonsSearch, SourceError


class EmptySearchAPI:
    def __init__(self, fail_prefix=False):
        self.calls = []
        self.fail_prefix = fail_prefix

    def json(self, url, **params):
        self.calls.append(params)
        if params.get('generator') == 'search':
            return {'query': {'pages': []}}
        if params.get('list') == 'allimages':
            if self.fail_prefix:
                raise SourceError('source_api_busy', 'Prefix service temporarily busy')
            return {'query': {'allimages': [{'title': 'File:陳湘琪2022.jpg'}]}}
        if params.get('titles') == 'File:陳湘琪2022.jpg':
            return {'query': {'pages': [{
                'title': 'File:陳湘琪2022.jpg',
                'imageinfo': [{
                    'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/test.jpg',
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:陳湘琪2022.jpg',
                    'width': 2400, 'height': 3600,
                    'extmetadata': {
                        'Artist': {'value': 'Example Photographer'},
                        'LicenseShortName': {'value': 'CC BY 4.0'},
                        'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by/4.0/'},
                        'ImageDescription': {'value': '陳湘琪 portrait'}
                    }
                }]
            }]}}
        raise AssertionError('Unexpected API request: ' + str(params))


class CommonsEmptyPrefixFallbackTest(unittest.TestCase):
    def test_three_character_chinese_name_recovers_exact_filename_metadata(self):
        api = EmptySearchAPI()
        rows = list(CommonsSearch().search({'name': '陳湘琪'}, api))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['filename'], '陳湘琪2022.jpg')
        self.assertEqual(rows[0]['identityEvidence']['query'], '陳湘琪')
        self.assertIn('identityWarning', rows[0]['identityEvidence'])
        prefix = [p for p in api.calls if p.get('list') == 'allimages']
        self.assertEqual(len(prefix), 1)
        self.assertEqual(prefix[0]['aiprefix'], '陳湘琪')
        self.assertEqual(prefix[0]['ailimit'], 8)

    def test_short_stage_name_does_not_fan_out_into_prefix_lookup(self):
        api = EmptySearchAPI()
        self.assertEqual(list(CommonsSearch().search({'name': '家家'}, api)), [])
        self.assertFalse(any(p.get('list') == 'allimages' for p in api.calls))

    def test_prefix_rate_limit_does_not_cancel_other_search_query(self):
        api = EmptySearchAPI(fail_prefix=True)
        rows = list(CommonsSearch().search({
            'name': '陳湘琪', 'reviewSearchQuery': '陳湘琪 演員'
        }, api))
        self.assertEqual(rows, [])
        self.assertEqual(sum(p.get('list') == 'allimages' for p in api.calls), 1)
        self.assertEqual(sum(p.get('generator') == 'search' for p in api.calls), 2)


if __name__ == '__main__':
    unittest.main()
