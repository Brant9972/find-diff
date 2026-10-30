"""Wikidata native-name (P1559) identity fallback must be exact and safe."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import EntityPortraits, SourceError


class NativeNameIdentityTest(unittest.TestCase):
    def _http(self, native_text='王大陸', language='zh-tw', rank='normal'):
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
                    return {'entities': {'Q15938098': {
                        # English-only label: the known Wikidata failure case.
                        'labels': {'en': {'value': 'Darren Wang'}},
                        'aliases': {},
                        'claims': {
                            'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}],
                            'P1559': [{'rank': rank, 'mainsnak': {'datavalue': {
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

    def test_wang_talu_lead_remains_draft_and_pinned(self):
        import json
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        row = next(p for p in plan['selectedNew']
                   if p['plannedQuestionId'] == 't1500_0181')
        self.assertEqual(row['wikidataId'], 'Q15938098')
        self.assertEqual(row['reviewExactCommonsFiles'], ['TaLu.jpg'])
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
