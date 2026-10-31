"""P373 is a bounded discovery hint, not permission or face identity evidence."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_pipeline.sources import EntityPortraits


class FakeHttp:
    def __init__(self):
        self.calls = []

    def json(self, url, **params):
        self.calls.append((url, params))
        if params.get('list') == 'categorymembers':
            return {'query': {'categorymembers': [
                {'title': 'File:Unrelated scene.jpg'},
                {'title': 'File:Yang event.jpg'},
                {'title': 'File:Unsafe.svg'},
            ]}}
        if params.get('titles') and 'File:' in params['titles']:
            return {'query': {'pages': [
                {'title': 'File:Unrelated scene.jpg', 'imageinfo': [
                    {'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Unrelated_scene.jpg',
                     'url': 'https://upload.wikimedia.org/wikipedia/commons/a/aa/Unrelated_scene.jpg',
                     'extmetadata': {'ImageDescription': {'value': 'An unrelated event'},
                                     'Artist': {'value': 'Test Photographer'},
                                     'LicenseShortName': {'value': 'CC BY 4.0'},
                                     'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by/4.0'}}}]},
                {'title': 'File:Yang event.jpg', 'imageinfo': [
                    {'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Yang_event.jpg',
                     'url': 'https://upload.wikimedia.org/wikipedia/commons/a/aa/Yang_event.jpg',
                     'extmetadata': {'ImageDescription': {'value': '楊昇達 at a public event'},
                                     'Artist': {'value': 'Test Photographer'},
                                     'LicenseShortName': {'value': 'CC BY 4.0'},
                                     'LicenseUrl': {'value': 'https://creativecommons.org/licenses/by/4.0'}}}]},
            ]}}
        if params.get('generator') == 'search':
            return {'query': {'pages': []}}
        if url.startswith('https://zh.wikipedia.org/'):
            return {'query': {'pages': [{'title': '楊昇達',
                                         'pageprops': {'wikibase_item': 'Q15934772'},
                                         'fullurl': 'https://zh.wikipedia.org/wiki/楊昇達'}]}}
        if params.get('action') == 'wbgetentities':
            return {'entities': {'Q15934772': {
                'labels': {'zh': {'value': '楊昇達'}, 'en': {'value': 'Yang Sheng-Da'}},
                'aliases': {},
                'claims': {
                    'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}],
                    'P373': [{'mainsnak': {'datavalue': {'value': 'Yang Shengda'}}}],
                },
            }}}
        raise AssertionError((url, params))


class P373CategoryFallbackTest(unittest.TestCase):
    def test_exact_q5_p373_enumeration_is_bounded_and_does_not_approve(self):
        http = FakeHttp()
        person = {'name': '楊昇達', 'acceptedAnswers': ['楊昇達'], 'wikidataId': 'Q15934772'}
        candidates = list(EntityPortraits(allow_openverse=False).search(person, http))
        listing = [args for _, args in http.calls if args.get('list') == 'categorymembers']
        self.assertEqual(len(listing), 1)
        self.assertEqual(listing[0]['cmtitle'], 'Category:Yang Shengda')
        self.assertEqual(listing[0]['cmtype'], 'file')
        self.assertLessEqual(listing[0]['cmlimit'], 12)
        exact_calls = [args for _, args in http.calls if 'titles' in args and
                       str(args['titles']).startswith('File:')]
        self.assertEqual(len(exact_calls), 1)
        self.assertNotIn('Unsafe.svg', exact_calls[0]['titles'])
        self.assertEqual(len(candidates), 2)
        named = next(x for x in candidates if x['filename'] == 'Yang event.jpg')
        unrelated = next(x for x in candidates if x['filename'] == 'Unrelated scene.jpg')
        self.assertIn('楊昇達', named['identityEvidence']['matchedAliases'])
        self.assertEqual(unrelated['identityEvidence']['matchedAliases'], [])
        self.assertNotIn('eligibleForLive', named)
        self.assertEqual(named['identityEvidence']['commonsCategoryEvidence'],
                         'Wikidata P373 on exact-name Q5 entity')


if __name__ == '__main__':
    unittest.main()
