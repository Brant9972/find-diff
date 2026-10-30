"""Pin entertainer Zhao Zhengping, not historical namesakes, without approving a crop."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.core import process
from media_pipeline.sources import CuratedCommons, rights


class ZhaoZhengpingSourceIdentityTest(unittest.TestCase):
    def setUp(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        self.person = next(row for row in plan['selectedNew']
                           if row['plannedQuestionId'] == 't1500_0102')

    def test_wikidata_and_curated_source_are_exact_and_unapproved(self):
        person = self.person
        self.assertEqual(person['name'], '趙正平')
        self.assertEqual(person['wikidataId'], 'Q9088389')
        self.assertEqual(person['photoStatus'], 'published')
        self.assertTrue(person['imageVerification']['finalCropReviewed'])
        self.assertTrue(person['imageVerification']['rightsDocumented'])
        rows = list(CuratedCommons().search(person, None))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['filename'],
                         'David Chao at Kinokuniya Taipei Breeze Store 20100102.jpg')
        self.assertEqual(rights(row), 'open_license_metadata')
        self.assertFalse(row['identityEvidence']['visualIdentityVerified'])
        self.assertTrue(person['sourceVerification']['posterFacesWarning'])

    def test_historical_namesake_sources_never_downloaded(self):
        person = self.person
        wrong = ['Zhao_Zhengping.jpg', 'Zhao_Zhengping.JPG']
        correct = list(CuratedCommons().search(person, None))[0]

        class Provider:
            name = 'commons'
            def search(self, person, http, round_number=0):
                for name in wrong:
                    yield {
                        'provider': 'commons',
                        'source': 'https://commons.wikimedia.org/wiki/File:' + name,
                        'url': 'https://upload.wikimedia.org/' + name,
                        'filename': name,
                        'caption': '趙正平，民國時期政治人物',
                        'artist': 'Fixture',
                        'license': 'CC BY-SA 4.0',
                        'licenseUrl': 'https://creativecommons.org/licenses/by-sa/4.0/',
                        'identityEvidence': {},
                    }
                yield correct

        class HTTP:
            budget = None
            def __init__(self):
                self.downloads = []
            def get(self, url):
                self.downloads.append(url)
                return b'fixture portrait bytes'

        def crop(blob):
            return b'fixture cropped jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1]}, {'size': [600, 720]}

        row = {'personId': 't1500_0102', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process(person, row, root, root / 'expansion-1500' / 'pipeline',
                    [Provider()], http, crop, set(), max_candidates=1,
                    max_attempts=3, active={}, rejected_pixels=[])
        self.assertEqual(http.downloads, [correct['url']])
        pending = [candidate for candidate in row['candidates']
                   if candidate['status'] == 'pending_review']
        self.assertEqual(len(pending), 1)
        self.assertFalse(pending[0]['eligibleForLive'])


if __name__ == '__main__':
    unittest.main()
