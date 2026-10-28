import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import CommonsSearch, Official, Openverse, Wikimedia, rights


class FixtureHTTP:
    def __init__(self):
        self.calls = []
    def json(self, url, **params):
        self.calls.append((url, params))
        if 'wikipedia.org' in url:
            return {'query': {'pages': [{'fullurl': 'https://zh.wikipedia.org/wiki/測試人物', 'extract': '測試人物是歌手。', 'pageimage': '測試人物.jpg', 'pageprops': {'wikibase_item': 'Q123'}}]}}
        if 'wikidata.org' in url:
            return {'entities': {'Q123': {'claims': {'P18': [{'mainsnak': {'datavalue': {'value': '測試人物.jpg'}}}]}}}}
        if params.get('generator'):
            return {'query': {'pages': [{'title': 'File:測試人物.jpg'}]}}
        return {'query': {'pages': [{'imageinfo': [{'url': 'https://upload.wikimedia.org/a.jpg', 'thumburl': 'https://upload.wikimedia.org/thumb/a/1400px-a.jpg', 'descriptionurl': 'https://commons.wikimedia.org/wiki/File:測試人物.jpg', 'width': 800, 'height': 1000,
                'extmetadata': {k: {'value': v} for k, v in {'LicenseShortName': 'CC BY 4.0', 'LicenseUrl': 'https://creativecommons.org/licenses/by/4.0/', 'Artist': '<b>Photographer</b>', 'ImageDescription': '測試人物在代表作舞台'}.items()}}]}]}}


class SourcesTest(unittest.TestCase):
    def test_wikimedia_combines_article_entity_and_search_without_duplicate(self):
        http = FixtureHTTP()
        rows = list(Wikimedia().search({'name': '測試人物', 'representativeWorks': ['代表作'], 'preferredImageQuery': '測試人物 代表作'}, http))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['artist'], 'Photographer')
        self.assertIn('/thumb/', rows[0]['url'])
        self.assertEqual(rows[0]['originalUrl'], 'https://upload.wikimedia.org/a.jpg')
        self.assertEqual(rights(rows[0]), 'open_license_metadata')
        self.assertEqual(rows[0]['recognitionEvidence']['matchedWorks'], ['代表作'])
        self.assertTrue(any('wikidata.org' in url for url, _ in http.calls))
        self.assertTrue(any(p.get('generator') == 'search' for _, p in http.calls))

    def test_commons_bulk_search_does_not_depend_on_wikipedia(self):
        class Bulk:
            def json(self,url,**params):
                assert url=='https://commons.wikimedia.org/w/api.php'
                assert params['prop']=='imageinfo'
                return {'query':{'pages':[{'title':'File:測試人物.jpg','imageinfo':[{'descriptionurl':'https://commons.wikimedia.org/wiki/File:測試人物.jpg','url':'https://upload.wikimedia.org/a.jpg','extmetadata':{'Artist':{'value':'Photographer'},'LicenseShortName':{'value':'CC BY 4.0'},'LicenseUrl':{'value':'http://creativecommons.org/licenses/by/4.0/'}}}]}]}}
        rows=list(CommonsSearch().search({'name':'測試人物'},Bulk()))
        self.assertEqual(len(rows),1)
        self.assertEqual(rights(rows[0]),'open_license_metadata')

    def test_openverse_preserves_original_landing_page_and_rights_warning(self):
        class API:
            def json(self, *args, **kwargs):
                return {'results': [{'url': 'https://provider.example/original.jpg', 'foreign_landing_url': 'https://provider.example/photo/1', 'creator': 'Creator', 'license': 'by-sa', 'license_version': '4.0', 'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/', 'title': '測試人物 portrait'}]}
        row = next(Openverse().search({'name': '測試人物'}, API()))
        self.assertEqual(row['source'], 'https://provider.example/photo/1')
        self.assertIn('rightsWarning', row)
        self.assertEqual(rights(row), 'open_license_metadata')

    def test_official_only_returns_explicit_person_sources_and_no_invented_licence(self):
        adapter = Official([{'personId': 't1', 'source': 'https://official.example/artist', 'license': 'Copyright retained'}, {'personId': 't2'}])
        rows = list(adapter.search({'plannedQuestionId': 't1'}, None))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rights(rows[0]), 'needs_review')


if __name__ == '__main__':
    unittest.main()
