"""李權哲 is two different singers; a licensed photo of Ely Li is not Jerry Li."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.sources import EntityPortraits, SourceError, excluded_commons_keys, source_key


class EntityAPI:
    def __init__(self, sitelink='李權哲 (台灣歌手)'):
        self.sitelink = sitelink
        self.calls = []
        self.verified_identities = {}

    def json(self, url, **params):
        self.calls.append((url, params))
        if 'zh.wikipedia.org' in url:
            # The ambiguous title can resolve to the *other* Chinese idol.
            return {'query': {'pages': [{
                'title': '李權哲 (中國大陸歌手)',
                'pageprops': {'wikibase_item': 'Q56259814'},
                'fullurl': 'https://zh.wikipedia.org/wiki/李權哲_(中國大陸歌手)',
            }]}}
        if params.get('action') == 'wbgetentities':
            assert params['ids'] == 'Q65046310', 'Do not fetch the namesake QID'
            return {'entities': {'Q65046310': {
                'labels': {'en': {'value': 'Jerry Li'}},
                'aliases': {},
                'sitelinks': {'zhwiki': {'title': self.sitelink}},
                'claims': {'P31': [{
                    'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}
                }]},
            }}}
        raise AssertionError(f'Unexpected request: {url} {params}')


class LiQuanzheHomonymTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        cls.person = next(row for row in plan['selectedNew']
                          if row['plannedQuestionId'] == 't1500_0395')

    def test_release_plan_pins_taiwanese_singer_not_loong9_idol(self):
        p = self.person
        self.assertEqual(p['wikidataId'], 'Q65046310')
        self.assertEqual(p['wikidataSitelinkTitle'], '李權哲 (台灣歌手)')
        self.assertIn('雲端司機', p['acceptedAnswers'])
        self.assertIn('愛情一陣風', p['representativeWorks'])
        self.assertIn('Ely Li', p['photoSearchBlockedEnglishAliases'])
        wrong = 'https://commons.wikimedia.org/wiki/File:Li_Quanzhe_20240609.jpg'
        self.assertIn(source_key(wrong), excluded_commons_keys(p))
        self.assertFalse(p.get('imageVerification', {}).get('faceMatchesPerson'))
        self.assertNotEqual(p.get('qaStatus'), 'releasable')

    def test_curator_pinned_exact_sitelink_bridges_missing_chinese_wikidata_label(self):
        api = EntityAPI()
        aliases, query, evidence, files = EntityPortraits()._resolve(self.person, api)
        self.assertEqual(evidence['wikidataId'], 'Q65046310')
        self.assertEqual(query, '李權哲')
        self.assertIn('Jerry Li', aliases)
        self.assertEqual(files, [])
        self.assertFalse(evidence['visualIdentityVerified'])
        self.assertFalse(any('Q56259814' == call[1].get('ids') for call in api.calls))

    def test_wrong_sitelink_cannot_be_used_as_identity_proof(self):
        api = EntityAPI(sitelink='李權哲 (中國大陸歌手)')
        with self.assertRaises(SourceError) as cm:
            EntityPortraits()._resolve(self.person, api)
        self.assertEqual(cm.exception.code, 'identity_unconfirmed')


if __name__ == '__main__':
    unittest.main()
