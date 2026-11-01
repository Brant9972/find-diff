"""Prevent actor 江華 / Kwong Wa(h) from searching unrelated hospital/bus stops."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import CommonsSearch, EntityPortraits


class IdentityAPI:
    def __init__(self):
        self.calls = []
        self.verified_identities = {}

    def json(self, url, **params):
        self.calls.append((url, params))
        if 'zh.wikipedia.org' in url:
            return {'query': {'pages': [{'title': '江華', 'pageprops': {'wikibase_item': 'Q5692593'}}]}}
        if 'en.wikipedia.org' in url:
            return {'query': {'pages': []}}
        if 'wikidata.org' in url:
            return {'entities': {'Q5692593': {
                'labels': {'zh': {'value': '江華'}, 'en': {'value': 'Kwong Wa'}},
                'aliases': {'en': [{'value': 'Kwong Wah'}]},
                'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]},
            }}}
        if 'commons.wikimedia.org' in url:
            return {'query': {'pages': []}}
        raise AssertionError('Unexpected URL: ' + url)


class JiangHuaEnglishHomonymTest(unittest.TestCase):
    def test_exact_qid_kept_but_hospital_aliases_not_photo_queries(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(x for x in plan['selectedNew'] if x['plannedQuestionId'] == 't1500_0583')
        self.assertEqual(person['wikidataId'], 'Q5692593')
        self.assertEqual(set(person['photoSearchBlockedEnglishAliases']), {'Kwong Wa', 'Kwong Wah'})
        api = IdentityAPI()
        aliases, query, evidence, files = EntityPortraits()._resolve(person, api)
        self.assertEqual(evidence['wikidataId'], 'Q5692593')
        self.assertEqual(query, '江華')
        self.assertEqual(aliases, ['江華'])
        self.assertEqual(files, [])
        list(CommonsSearch().search(person, api))
        searches = [p['gsrsearch'] for u, p in api.calls if 'commons.wikimedia.org' in u and 'gsrsearch' in p]
        self.assertTrue(searches)
        self.assertTrue(all('Kwong Wa' not in x and 'Kwong Wah' not in x for x in searches))
        self.assertTrue(any('江華' in x for x in searches))


if __name__ == '__main__':
    unittest.main()
