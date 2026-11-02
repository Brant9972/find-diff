"""Wikidata native-name (P1559) identity fallback must be exact and safe."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import EntityPortraits, SourceError


class NativeNameIdentityTest(unittest.TestCase):
    def _http(self, native_text='王大陸', language='zh-tw', rank='normal', property_id='P1559'):
        class HTTP:
            def json(self, url, **kwargs):
                if 'zh.wikipedia.org' in url:
                    return {'query': {'pages': [{
                        'title': '王大陸',
                        'pageprops': {'wikibase_item': 'Q15938098'},
                        'fullurl': 'https://zh.wikipedia.org/wiki/王大陸',
                    }]}}
                if kwargs.get('action') == 'wbgetentities':
                    self_requested = kwargs['ids']
                    assert self_requested == 'Q15938098'
                    assert 'zh-hk' in kwargs['languages'] and 'zh-mo' in kwargs['languages']
                    return {'entities': {'Q15938098': {
                        # English-only label: the known Wikidata failure case.
                        'labels': {'en': {'value': 'Darren Wang'}},
                        'aliases': {},
                        'claims': {
                            'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}],
                            property_id: [{'rank': rank, 'mainsnak': {'datavalue': {
                                'value': {'text': native_text, 'language': language}}}}],
                            'P18': [{'mainsnak': {'datavalue': {'value': 'TaLu.jpg'}}}],
                        },
                    }}}
                raise AssertionError('Unexpected lookup ' + url)
        return HTTP()

    def test_exact_chinese_native_name_allows_pinned_p18_discovery(self):
        person = {'name': '王大陸', 'acceptedAnswers': ['王大陸', 'Darren Wang'],
                  'wikidataId': 'Q15938098'}
        aliases, query, evidence, files = EntityPortraits()._resolve(person, self._http())
        self.assertEqual(query, '王大陸')
        self.assertEqual(evidence['wikidataId'], 'Q15938098')
        self.assertEqual(evidence['entityTypeEvidence'], 'P31=Q5')
        self.assertFalse(evidence['visualIdentityVerified'])
        self.assertIn('王大陸', aliases)
        self.assertIn('Darren Wang', aliases)
        self.assertEqual(files, ['TaLu.jpg'])

    def test_exact_chinese_birth_name_or_nickname_is_search_only(self):
        person = {'name': '王大陸', 'wikidataId': 'Q15938098'}
        for property_id in ('P1477', 'P1449'):
            with self.subTest(property_id=property_id):
                aliases, query, evidence, files = EntityPortraits()._resolve(
                    person, self._http(property_id=property_id, language='zh-hk'))
                self.assertIn('王大陸', aliases)
                self.assertEqual(query, '王大陸')
                self.assertEqual(files, ['TaLu.jpg'])
                self.assertFalse(evidence['visualIdentityVerified'])
                self.assertEqual(evidence['entityTypeEvidence'], 'P31=Q5')

    def test_birth_name_or_nickname_cannot_match_partial_or_deprecated(self):
        person = {'name': '王大陸', 'wikidataId': 'Q15938098'}
        for property_id in ('P1477', 'P1449'):
            for native_text, language, rank in [
                ('王大陸交通', 'zh-hk', 'normal'),
                ('王大陸', 'en', 'normal'),
                ('王大陸', 'zh-hk', 'deprecated'),
            ]:
                with self.subTest(property_id=property_id, native_text=native_text,
                                  language=language, rank=rank):
                    with self.assertRaises(SourceError) as caught:
                        EntityPortraits()._resolve(
                            person, self._http(native_text, language, rank, property_id))
                    self.assertEqual(caught.exception.code, 'identity_unconfirmed')

    def test_wang_talu_lead_remains_draft_and_pinned(self):
        import json
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        row = next(p for p in plan['selectedNew']
                   if p['plannedQuestionId'] == 't1500_0181')
        self.assertEqual(row['wikidataId'], 'Q15938098')
        self.assertIn('https://commons.wikimedia.org/wiki/File:TaLu.jpg',
                      row['excludedPhotoSources'])
        self.assertFalse(row.get('reviewExactCommonsFiles'))
        self.assertNotEqual(row['photoStatus'], 'published')
        self.assertFalse(row['imageVerification']['finalCropReviewed'])
        self.assertFalse(row['imageVerification']['imageAdjacentCaptionVerified'])

    def test_nonmatching_native_name_does_not_override_identity(self):
        person = {'name': '王大陸', 'wikidataId': 'Q15938098'}
        for text, language, rank in [
            ('王大陸交通', 'zh-tw', 'normal'),
            ('王大陸', 'en', 'normal'),
            ('王大陸', 'zh-tw', 'deprecated'),
        ]:
            with self.subTest(text=text, language=language, rank=rank):
                with self.assertRaises(SourceError) as caught:
                    EntityPortraits()._resolve(
                        person, self._http(text, language, rank))
                self.assertEqual(caught.exception.code, 'identity_unconfirmed')


if __name__ == '__main__':
    unittest.main()
