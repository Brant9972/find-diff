"""Regression fixtures for real batch failures: busy search and lost aliases."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import EntityPortraits, Openverse, SourceError, rights


def human(qid='Q123', chinese='測試人物', english='Test Artist'):
    return {'id': qid,
            'labels': {'zh': {'value': chinese}, 'en': {'value': english}},
            'aliases': {'en': [{'value': 'Artist Test'}]},
            'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]}}


class RetryAPI:
    """No network: exact title metadata, entity metadata, and two image catalogues."""
    def __init__(self, page=None, entities=None, search_error=None, unrelated=False):
        self.page = page if page is not None else {
            'pageid': 123, 'title': '測試人物',
            'fullurl': 'https://zh.wikipedia.org/wiki/測試人物',
            'pageprops': {'wikibase_item': 'Q123'}}
        self.entities = entities or {'Q123': human()}
        self.search_error = search_error
        self.unrelated = unrelated
        self.calls = []
        self.verified_identities = {}

    def json(self, url, **params):
        self.calls.append((url, copy.deepcopy(params)))
        if 'zh.wikipedia.org' in url:
            return {'query': {'pages': [copy.deepcopy(self.page)]}}
        if params.get('action') == 'wbsearchentities':
            if self.search_error:
                raise self.search_error
            return {'search': [{'id': qid} for qid in self.entities]}
        if params.get('action') == 'wbgetentities':
            ids = params['ids'].split('|')
            return {'entities': {qid: copy.deepcopy(self.entities[qid]) for qid in ids if qid in self.entities}}
        if 'Special:EntityData' in url:
            qid = url.rsplit('/', 1)[-1].removesuffix('.json')
            return {'entities': {qid: copy.deepcopy(self.entities[qid])}}
        if 'commons.wikimedia.org' in url:
            name = 'Different_Celebrity' if self.unrelated else 'Test_Artist'
            return {'query': {'pages': [{
                'title': 'File:' + name + '_portrait.jpg',
                'imageinfo': [{
                    'url': 'https://upload.wikimedia.org/' + name + '.jpg',
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:' + name + '.jpg',
                    'width': 1800, 'height': 2200,
                    'extmetadata': {key: {'value': value} for key, value in {
                        'Artist': 'Source Photographer', 'LicenseShortName': 'CC BY 4.0',
                        'LicenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                        'ImageDescription': name.replace('_', ' ') + ' formal portrait'}.items()}}]}]}}
        if 'openverse.org' in url:
            name = 'Different_Celebrity' if self.unrelated else 'Test_Artist'
            return {'results': [{
                'url': 'https://photos.example.org/' + name + '.jpg',
                'foreign_landing_url': 'https://photos.example.org/photo/123',
                'title': name.replace('_', ' ') + ' formal portrait',
                'creator': 'Independent Photographer',
                'license': 'by', 'license_version': '4.0',
                'license_url': 'https://creativecommons.org/licenses/by/4.0/'}]}
        raise AssertionError('Unexpected API request: ' + url + ' ' + str(params))


class SourceRetryRegressionTest(unittest.TestCase):
    person = {'name': '測試人物', 'aliases': [], 'representativeWorks': ['代表作']}

    def test_exact_wikipedia_qid_bypasses_busy_cirrus_search(self):
        api = RetryAPI(search_error=SourceError('source_api_error', 'cirrussearch-too-busy-error'))
        rows = list(EntityPortraits().search(self.person, api))
        self.assertTrue(rows)
        first_url, params = api.calls[0]
        self.assertIn('zh.wikipedia.org', first_url)
        self.assertEqual(params.get('titles'), self.person['name'])
        self.assertIn('pageprops', params.get('prop', ''))
        self.assertFalse(any(params.get('action') == 'wbsearchentities' for _, params in api.calls))
        self.assertTrue(all(row['identityEvidence']['wikidataId'] == 'Q123' for row in rows))

    def test_missing_exact_article_falls_back_to_entity_search(self):
        api = RetryAPI(page={'title': self.person['name'], 'missing': True})
        self.assertTrue(list(EntityPortraits().search(self.person, api)))
        self.assertTrue(any(params.get('action') == 'wbsearchentities' for _, params in api.calls))

    def test_disambiguation_page_does_not_select_one_same_name_human(self):
        api = RetryAPI(page={'title': self.person['name'],
                            'pageprops': {'wikibase_item': 'Q123', 'disambiguation': ''}},
                       entities={'Q123': human(), 'Q456': human('Q456', english='Another Artist')})
        with self.assertRaises(SourceError) as raised:
            list(EntityPortraits().search(self.person, api))
        self.assertEqual(raised.exception.code, 'identity_ambiguous')
        self.assertFalse(any('commons.wikimedia.org' in url or 'openverse.org' in url for url, _ in api.calls))

    def test_exact_article_does_not_bypass_entity_q5_check(self):
        company = human()
        company['claims']['P31'][0]['mainsnak']['datavalue']['value']['id'] = 'Q43229'
        api = RetryAPI(entities={'Q123': company})
        with self.assertRaises(SourceError):
            list(EntityPortraits().search(self.person, api))
        self.assertFalse(any('commons.wikimedia.org' in url or 'openverse.org' in url for url, _ in api.calls))

    def test_exact_article_does_not_bypass_chinese_name_check(self):
        api = RetryAPI(entities={'Q123': human(chinese='不同人物')})
        with self.assertRaises(SourceError):
            list(EntityPortraits().search(self.person, api))
        self.assertFalse(any('commons.wikimedia.org' in url or 'openverse.org' in url for url, _ in api.calls))

    def test_closing_entity_generator_keeps_alias_for_independent_openverse(self):
        api = RetryAPI()
        discovery = EntityPortraits().search(self.person, api)
        next(discovery)
        discovery.close()
        api.calls.clear()
        rows = list(Openverse().search(self.person, api))
        self.assertTrue(rows)
        queries = [params['q'] for url, params in api.calls if 'openverse.org' in url]
        self.assertTrue(queries)
        self.assertIn('Test Artist', queries[0])
        self.assertNotIn(self.person['name'], queries[0])
        self.assertEqual(rows[0]['identityEvidence'].get('wikidataId'), 'Q123')
        self.assertIn('Test Artist', rows[0]['identityEvidence'].get('matchedAliases', []))
        self.assertIsNot(rows[0]['identityEvidence'].get('visualIdentityVerified'), True)
        self.assertEqual(rights(rows[0]), 'open_license_metadata')

    def test_verified_english_commons_query_is_complete_name_phrase(self):
        api = RetryAPI()
        list(EntityPortraits().search(self.person, api))
        queries = [params['gsrsearch'] for url, params in api.calls
                   if 'commons.wikimedia.org' in url and 'gsrsearch' in params]
        self.assertTrue(queries)
        self.assertTrue(any('"Test Artist"' in query for query in queries), queries)

    def test_cached_identity_does_not_label_unrelated_openverse_photo(self):
        api = RetryAPI()
        discovery = EntityPortraits().search(self.person, api)
        next(discovery)
        discovery.close()
        api.unrelated = True
        rows = list(Openverse().search(self.person, api))
        self.assertTrue(rows)
        self.assertFalse(any(row['identityEvidence'].get('matchedAliases') for row in rows))
        self.assertFalse(any(row['identityEvidence'].get('visualIdentityVerified') is True for row in rows))

    def test_another_person_does_not_inherit_previous_verified_alias(self):
        api = RetryAPI()
        discovery = EntityPortraits().search(self.person, api)
        next(discovery)
        discovery.close()
        api.calls.clear()
        list(Openverse().search({'name': '另外一人', 'aliases': []}, api))
        queries = [params['q'] for url, params in api.calls if 'openverse.org' in url]
        self.assertEqual(queries, ['另外一人'])

    def test_reliable_identity_precedes_unrelated_rows_with_limited_provider_cap(self):
        api = RetryAPI()
        original = api.json
        def crowded_commons(url, **params):
            data = original(url, **params)
            if 'commons.wikimedia.org' not in url:
                return data
            proper = data['query']['pages'][0]
            unrelated = []
            for index in range(5):
                row = copy.deepcopy(proper)
                row['title'] = 'File:A_Unknown_' + str(index) + '_portrait.jpg'
                info = row['imageinfo'][0]
                info['descriptionurl'] += '?unrelated=' + str(index)
                info['extmetadata']['ImageDescription']['value'] = 'An unrelated person'
                unrelated.append(row)
            data['query']['pages'] = unrelated + [proper]
            return data
        api.json = crowded_commons
        rows = list(EntityPortraits().search(self.person, api))
        self.assertTrue(rows)
        self.assertIn('Test Artist', rows[0]['identityEvidence'].get('matchedAliases', []),
                      'Four unrelated rows must not consume all provider slots before a reliable match')


if __name__ == '__main__':
    unittest.main()
