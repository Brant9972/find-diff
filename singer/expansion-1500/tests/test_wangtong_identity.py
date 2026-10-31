"""Regression: 王瞳 (Hitomi Wu) must not inherit Wang Tong namesakes' photos."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import EntityPortraits, identity


ROOT = Path(__file__).resolve().parents[1]


class WangTongIdentityTest(unittest.TestCase):
    def person(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        return next(p for p in plan['selectedNew']
                    if p['plannedQuestionId'] == 't1500_0007')

    def test_curated_qid_and_conflicting_namesakes(self):
        person = self.person()
        self.assertEqual(person['name'], '王瞳')
        self.assertEqual(person['wikidataId'], 'Q9066373')
        self.assertEqual(set(person['photoSearchBlockedEnglishAliases']),
                         {'Wang Tong', 'Tong Wang'})
        self.assertTrue({'王童', '王彤', '王統'}.issubset(
            set(person['excludedCaptionNames'])))
        self.assertEqual(identity(person, '導演王童接受專訪'), [])
        self.assertEqual(identity(person, '足球員王彤效力山東泰山'), [])
        self.assertEqual(identity(person, '王瞳 2024 portrait'), ['王瞳'])
        self.assertFalse(person['imageVerification']['finalCropReviewed'])
        self.assertEqual(person['qaStatus'], 'not_releasable')

    def test_pinned_entity_never_searches_ambiguous_romanizations(self):
        person = self.person()

        class HTTP:
            def __init__(self):
                self.calls = []

            def json(self, url, **params):
                self.calls.append((url, params))
                if 'zh.wikipedia.org' in url:
                    return {'query': {'pages': [{
                        'title': '王瞳',
                        'pageprops': {'wikibase_item': 'Q9066373'},
                        'fullurl': 'https://zh.wikipedia.org/wiki/王瞳'
                    }]}}
                if params.get('action') == 'wbgetentities':
                    self_qid = 'Q9066373'
                    self.assertEqual(params['ids'], self_qid)
                    return {'entities': {self_qid: {
                        'labels': {'en': {'value': 'Hitomi Wu'}},
                        'aliases': {'en': [{'value': 'Wang Tong'},
                                           {'value': 'Tong Wang'},
                                           {'value': 'Hitomi Wang'}]},
                        'claims': {
                            'P31': [{'mainsnak': {'datavalue': {
                                'value': {'id': 'Q5'}}}}],
                            'P1559': [{'mainsnak': {'datavalue': {
                                'value': {'language': 'zh', 'text': '王瞳'}}}}],
                        }
                    }}}
                if 'commons.wikimedia.org' in url:
                    return {'query': {'pages': []}}
                raise AssertionError('Unexpected source: ' + url)

            def assertEqual(self, a, b):
                if a != b:
                    raise AssertionError(f'{a} != {b}')

        http = HTTP()
        self.assertEqual(list(EntityPortraits(allow_openverse=False).search(
            person, http)), [])
        searches = [p['gsrsearch'] for url, p in http.calls
                    if 'commons.wikimedia.org' in url
                    and p.get('generator') == 'search']
        self.assertIn('"王瞳" filetype:bitmap', searches)
        self.assertIn('"Hitomi Wu" filetype:bitmap', searches)
        self.assertFalse(any('Wang Tong' in q or 'Tong Wang' in q
                             for q in searches))
        self.assertFalse(any('Q9314433' in str(p) for _, p in http.calls))


if __name__ == '__main__':
    unittest.main()
