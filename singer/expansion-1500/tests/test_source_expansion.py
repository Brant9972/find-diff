"""Source expansion contracts: verified alias mapping and bounded failure isolation."""
import copy
import re
import sys
import time
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import CommonsSearch, EntityPortraits, HTTP, SourceError, rights


def entity(qid='Q123', human=True, english='Test Artist'):
    return {
        'id': qid,
        'labels': {'zh': {'language': 'zh', 'value': '測試人物'},
                   'en': {'language': 'en', 'value': english}},
        'aliases': {'en': [{'language': 'en', 'value': 'Artist Test'}],
                    'zh': [{'language': 'zh', 'value': '測試藝人'}]},
        'descriptions': {'zh': {'language': 'zh', 'value': '演員與歌手'}},
        'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5' if human else 'Q43229'}}}}]},
    }


class EntityAPI:
    def __init__(self, entities=None, commons_error=False, unrelated_caption=False):
        self.entities = entities or {'Q123': entity()}
        self.commons_error = commons_error
        self.unrelated_caption = unrelated_caption
        self.calls = []

    def json(self, url, **params):
        self.calls.append((url, params))
        if 'zh.wikipedia.org' in url:
            return {'query': {'pages': [{'title': '測試人物', 'missing': True}]}}
        if params.get('action') == 'wbsearchentities':
            return {'search': [{'id': qid, 'label': row['labels']['zh']['value'],
                                'description': '演員與歌手',
                                'match': {'type': 'label', 'text': row['labels']['zh']['value']}}
                               for qid, row in self.entities.items()]}
        if params.get('action') == 'wbgetentities':
            ids = params.get('ids', '|'.join(self.entities)).split('|')
            return {'entities': {qid: copy.deepcopy(self.entities[qid]) for qid in ids if qid in self.entities}}
        if 'Special:EntityData/' in url:
            qid = re.search(r'/Q(\d+)', url).group(0)[1:]
            return {'entities': {qid: copy.deepcopy(self.entities[qid])}}
        if 'commons.wikimedia.org' in url:
            if self.commons_error:
                raise SourceError('http_403', 'Fixture Commons refusal')
            title = 'Other_Person.jpg' if self.unrelated_caption else 'Test_Artist_portrait.jpg'
            caption = 'A different person' if self.unrelated_caption else 'Test Artist in a portrait session'
            return {'query': {'pages': [{
                'title': 'File:' + title,
                'imageinfo': [{
                    'url': 'https://upload.wikimedia.org/original/' + title,
                    'thumburl': 'https://upload.wikimedia.org/thumb/' + title,
                    'descriptionurl': 'https://commons.wikimedia.org/wiki/File:' + title,
                    'width': 1800, 'height': 2200,
                    'extmetadata': {key: {'value': value} for key, value in {
                        'Artist': 'Source Photographer',
                        'LicenseShortName': 'CC BY 4.0',
                        'LicenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                        'ImageDescription': caption,
                        'GPSLatitude': 22.3,
                    }.items()},
                }],
            }]}}
        if 'openverse.org' in url:
            return {'results': [{
                'url': 'https://photos.example.org/Test_Artist.jpg',
                'foreign_landing_url': 'https://photos.example.org/photo/123',
                'title': 'A different person' if self.unrelated_caption else 'Test Artist formal portrait',
                'creator': 'Independent Photographer',
                'license': 'by', 'license_version': '4.0',
                'license_url': 'https://creativecommons.org/licenses/by/4.0/',
            }]}
        raise AssertionError('Unexpected source request: ' + url)


class SourceExpansionTest(unittest.TestCase):
    person = {'name': '測試人物', 'aliases': [], 'representativeWorks': ['代表作']}

    def rejected_identity(self, api):
        try:
            rows = list(EntityPortraits().search(self.person, api))
        except SourceError:
            rows = []
        self.assertEqual(rows, [])
        self.assertFalse(any('commons.wikimedia.org' in url or 'openverse.org' in url for url, _ in api.calls))

    def test_verified_english_aliases_are_searched_and_provenance_is_kept(self):
        api = EntityAPI()
        rows = list(EntityPortraits().search(self.person, api))
        self.assertTrue(rows)
        self.assertTrue(any('Test Artist' in str(params.get('gsrsearch', params.get('q', '')))
                            for _, params in api.calls))
        for row in rows:
            evidence = row['identityEvidence']
            self.assertIn('Test Artist', evidence.get('matchedAliases', []))
            self.assertEqual(evidence.get('wikidataId'), 'Q123')
            self.assertIsNot(evidence.get('visualIdentityVerified'), True)
            self.assertEqual(rights(row), 'open_license_metadata')
            self.assertTrue(row['source'].startswith('https://'))
            self.assertTrue(row['artist'])

    def test_entity_p18_and_native_name_are_checked_before_english_homonyms(self):
        # A verified romanization may name many other people. Exact P18
        # lookup is first, Chinese native-name search second, English last.
        row = entity(english='Test Artist')
        row['claims']['P18'] = [{
            'mainsnak': {'datavalue': {'value': 'Test Artist portrait.jpg'}}
        }]
        api = EntityAPI(entities={'Q123': row})
        list(EntityPortraits().search(self.person, api))
        commons = [params for url, params in api.calls
                   if 'commons.wikimedia.org' in url]
        self.assertEqual(commons[0].get('titles'), 'File:Test Artist portrait.jpg')
        searches = [params['gsrsearch'] for params in commons
                    if params.get('generator') == 'search']
        self.assertEqual(searches[:2], [
            '"測試人物" filetype:bitmap',
            '"Test Artist" filetype:bitmap',
        ])
        self.assertEqual(searches.count('"測試人物" filetype:bitmap'), 1)
        self.assertTrue(all(params['gsrlimit'] <= 12 for params in commons
                            if params.get('generator') == 'search'))

    def test_entity_without_p18_still_queries_native_name_first(self):
        api = EntityAPI()
        list(EntityPortraits().search(self.person, api))
        searches = [params['gsrsearch'] for url, params in api.calls
                    if 'commons.wikimedia.org' in url and
                    params.get('generator') == 'search']
        self.assertEqual(searches[0], '"測試人物" filetype:bitmap')
        self.assertIn('"Test Artist" filetype:bitmap', searches[1:])

    def test_blocked_english_alias_does_not_search_unrelated_historical_name(self):
        # Actress 韓瑜 shares the romanization Han Yu with a historical poet.
        # Do not retrieve temples, poems and monuments as her portraits.
        api = EntityAPI(entities={'Q123': entity(english='Han Yu')})
        person = {**self.person, 'photoSearchBlockedEnglishAliases': ['Han Yu']}
        list(EntityPortraits().search(person, api))
        search_queries = [str(params.get('gsrsearch', params.get('q', '')))
                          for url, params in api.calls
                          if 'commons.wikimedia.org' in url or 'openverse.org' in url]
        self.assertTrue(search_queries)
        self.assertFalse(any('Han Yu' in query for query in search_queries))

    def test_han_yu_release_plan_has_identity_collision_guard(self):
        import json
        plan = json.loads((Path(__file__).resolve().parents[1] /
                           'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(p for p in plan['selectedNew']
                      if p['plannedQuestionId'] == 't1500_0216')
        self.assertEqual(person['name'], '韓瑜')
        self.assertIn('Han Yu', person['photoSearchBlockedEnglishAliases'])

    def test_ambiguous_same_name_humans_do_not_produce_portraits(self):
        self.rejected_identity(EntityAPI({'Q123': entity(), 'Q456': entity('Q456', english='Another Artist')}))

    def test_nonhuman_entity_does_not_produce_portraits(self):
        self.rejected_identity(EntityAPI({'Q123': entity(human=False)}))

    def test_search_hit_alone_does_not_become_identity_match(self):
        api = EntityAPI(unrelated_caption=True)
        # Openverse's filename is also unrelated for this case.
        original = api.json
        def unrelated(url, **params):
            data = original(url, **params)
            if 'openverse.org' in url:
                data['results'][0]['url'] = 'https://photos.example.org/Other_Person.jpg'
            return data
        api.json = unrelated
        rows = list(EntityPortraits().search(self.person, api))
        self.assertFalse(any(row.get('identityEvidence', {}).get('matchedAliases') for row in rows))
        self.assertFalse(any(row.get('identityEvidence', {}).get('visualIdentityVerified') is True for row in rows))

    def test_entity_provider_does_not_implicitly_call_openverse(self):
        # Explicit providers=[entity, commons] must not hit Openverse.
        api = EntityAPI()
        self.assertTrue(list(EntityPortraits().search(self.person, api)))
        self.assertFalse(any('openverse.org' in url for url, _ in api.calls))
        # The separate Openverse adapter remains available when selected.
        from media_pipeline.sources import Openverse
        self.assertTrue(list(Openverse().search(self.person, api)))
        self.assertTrue(any('openverse.org' in url for url, _ in api.calls))

    def test_commons_refusal_does_not_prevent_independent_openverse_search(self):
        api = EntityAPI(commons_error=True)
        with self.assertRaises(SourceError):
            list(EntityPortraits().search(self.person, api))
        self.assertFalse(any('openverse.org' in url for url, _ in api.calls))
        from media_pipeline.sources import Openverse
        rows = list(Openverse().search(self.person, api))
        self.assertTrue(any(row.get('source', '').startswith('https://photos.example.org/') for row in rows))
        self.assertTrue(any('openverse.org' in url for url, _ in api.calls))


class CommonsQueryPriorityTest(unittest.TestCase):
    def test_exact_chinese_name_precedes_verified_english_aliases(self):
        from media_pipeline.sources import identity_key
        class EmptyCommonsAPI:
            def __init__(self):
                context = {'aliases': ['測試人物', 'Test Artist'],
                           'englishAliases': ['Test Artist', 'Other Artist'],
                           'evidence': {'wikidataId': 'Q123', 'entityTypeEvidence': 'P31=Q5'}}
                self.verified_identities = {identity_key({'name': '測試人物'}): context}
                self.search_queries = []

            def json(self, url, **params):
                if params.get('generator') == 'search':
                    self.search_queries.append(params['gsrsearch'])
                    return {'query': {'pages': []}}
                raise AssertionError('Unexpected request: ' + str(params))

        api = EmptyCommonsAPI()
        person = {'name': '測試人物', 'reviewSearchQuery': '測試人物 演員'}
        self.assertEqual(list(CommonsSearch().search(person, api)), [])
        self.assertEqual(api.search_queries, [
            '"測試人物" filetype:bitmap',
            '"測試人物 演員" filetype:bitmap',
            '"Test Artist" filetype:bitmap',
            '"Other Artist" filetype:bitmap',
        ])

    def test_unverified_english_aliases_are_not_promoted(self):
        class EmptyCommonsAPI:
            verified_identities = {}
            def __init__(self):
                self.search_queries = []
            def json(self, url, **params):
                self.search_queries.append(params['gsrsearch'])
                return {'query': {'pages': []}}
        api = EmptyCommonsAPI()
        list(CommonsSearch().search({'name': '韓瑜', 'aliases': ['Han Yu']}, api))
        self.assertEqual(api.search_queries, ['"韓瑜" filetype:bitmap'])


class Response:
    def __init__(self, body=b'image bytes'):
        self.body = body
        self.offset = 0
        self.headers = {'Content-Length': str(len(body))}
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size=-1):
        if size < 0: size = len(self.body)
        result = self.body[self.offset:self.offset+size]
        self.offset += len(result)
        return result


class HTTPFailureBoundTest(unittest.TestCase):
    def assert_host_circuit(self, code):
        headers = Message()
        headers['Retry-After'] = '120'
        opener = mock.Mock()
        opener.open.side_effect = [urllib.error.HTTPError('https://blocked.example.org/a', code, 'Fixture refusal', headers, None), Response()]
        client = HTTP(attempts=3, interval=0, timeout=2)
        with mock.patch('media_pipeline.sources.urllib.request.build_opener', return_value=opener), mock.patch('media_pipeline.sources.time.sleep') as sleep:
            with self.assertRaises(SourceError) as first:
                client.get('https://blocked.example.org/a')
            self.assertEqual(first.exception.code, 'http_' + str(code))
            with self.assertRaises(SourceError):
                client.get('https://blocked.example.org/b')
            self.assertEqual(opener.open.call_count, 1, 'Same-host forbidden/rate-limited requests must not repeat in the batch')
            self.assertEqual(client.get('https://another.example.org/a'), b'image bytes')
            self.assertEqual(opener.open.call_count, 2, 'A source refusal must not disable independent hosts')
            self.assertFalse(any(call.args and call.args[0] > 0 for call in sleep.call_args_list), '403/429 should move on rather than sleeping the worker')

    def test_http_403_opens_host_circuit(self): self.assert_host_circuit(403)
    def test_http_429_opens_host_circuit(self): self.assert_host_circuit(429)

    def test_expired_budget_performs_no_request(self):
        client = HTTP(attempts=3, interval=0, budget=time.monotonic()-1, timeout=8)
        with mock.patch('media_pipeline.sources.urllib.request.build_opener') as build:
            with self.assertRaises(SourceError) as error:
                client.get('https://example.org/image.jpg')
            self.assertEqual(error.exception.code, 'time_budget')
            build.assert_not_called()

    def test_request_socket_timeout_is_capped_by_remaining_budget(self):
        opener = mock.Mock()
        opener.open.return_value = Response()
        client = HTTP(attempts=1, interval=0, budget=time.monotonic()+.5, timeout=8)
        with mock.patch('media_pipeline.sources.urllib.request.build_opener', return_value=opener):
            self.assertEqual(client.get('https://example.org/image.jpg'), b'image bytes')
        self.assertLessEqual(opener.open.call_args.kwargs['timeout'], .5)
        self.assertGreater(opener.open.call_args.kwargs['timeout'], 0)


if __name__ == '__main__':
    unittest.main()
