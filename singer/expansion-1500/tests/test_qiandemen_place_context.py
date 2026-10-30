"""Prevent same-name architectural sites being mistaken for actor 乾德門."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process


class QiandemenPlaceContextTest(unittest.TestCase):
    def test_gate_and_building_sources_are_not_downloaded(self):
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        person = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0208')
        self.assertEqual(person['name'], '乾德門')
        self.assertIn('Qiande Gate', person['excludedCaptionNames'])
        self.assertEqual(len(person['excludedPhotoSources']), 2)

        sources = [
            ('HK_KinTakHouse_KinTakMun.JPG', '乾德門與乾德樓'),
            ('Liao_Shangjing_2017_north_wall_archaeological_dig.jpg',
             'Archaeological dig at the Qiande Gate (乾德門)'),
            ('Actor_Chien_Te-men.jpg', '演員乾德門接受專訪'),
        ]

        class Provider:
            name = 'commons'
            def search(self, person, http, round_number=0):
                for filename, caption in sources:
                    yield {
                        'provider': 'commons',
                        'source': 'https://commons.wikimedia.org/wiki/File:' + filename,
                        'url': 'https://upload.wikimedia.org/' + filename,
                        'filename': filename,
                        'caption': caption,
                        'artist': 'Fixture photographer',
                        'license': 'CC BY 4.0',
                        'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                        'identityEvidence': {},
                    }

        class HTTP:
            budget = None
            def __init__(self): self.downloads = []
            def get(self, url):
                self.downloads.append(url)
                return b'fixture actor image'

        def crop(blob):
            return b'fixture 600x720 jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1],
            }, {'size': [600, 720]}

        row = {'personId': 't1500_0208', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'expansion-1500/pipeline'
            process(person, row, Path(tmp), directory, [Provider()], http,
                    crop, set(), max_candidates=1, active={}, rejected_pixels=[])
        self.assertEqual(http.downloads, ['https://upload.wikimedia.org/Actor_Chien_Te-men.jpg'])
        self.assertEqual([c['filename'] for c in row['candidates']
                          if c['status'] == 'pending_review'], ['Actor_Chien_Te-men.jpg'])
        self.assertTrue(all(c.get('eligibleForLive') is False for c in row['candidates']))


if __name__ == '__main__':
    unittest.main()
