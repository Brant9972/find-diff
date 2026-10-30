"""Regression: namesakes of places/businesses are not portrait evidence."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import obvious_nonportrait_scene, process


def candidate(filename, caption, source_id):
    return {
        'provider': 'commons',
        'source': 'https://commons.wikimedia.org/wiki/File:' + source_id,
        'url': 'https://upload.wikimedia.org/wikipedia/commons/' + source_id,
        'filename': filename,
        'caption': caption,
        'artist': 'Fixture photographer',
        'license': 'CC BY 4.0',
        'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
        'identityEvidence': {'verifiedSearchAliases': ['大元', 'Dayuan']},
    }


class NonPortraitSceneGuardTest(unittest.TestCase):
    def test_reject_obvious_places_and_businesses(self):
        scenes = [
            ('Dayuan District 201506.jpg', 'Dayuan District'),
            ('2010 07 Dayuan Township.JPG', 'Dayuan Township fishing harbor'),
            ("Wang Chung-Huang's Restaurant.jpg", '王中皇的店，雨中外觀'),
            ('Temple of Han Yu.jpg', 'Temple of Han Yu in Chaozhou'),
            ('20230207 Temple of Han Yu 02.jpg', 'Han Yu Temple'),
            ('HK CWB Sugar Street construction site.jpg', 'Paul Chun Pui 秦沛'),
            ('銘傳大學7147.jpg', '李銓校長於1999年接任校長'),
            ('HK auction 黃一山.jpg', 'Auction preview'),
            ('New Wang Tong River Bridge 2025.jpg', 'New river bridge'),
            ('香港家家美食餐廳.jpg', 'Ka Ka Cuisine Restaurant'),
        ]
        for filename, caption in scenes:
            with self.subTest(filename=filename):
                self.assertTrue(obvious_nonportrait_scene(
                    candidate(filename, caption, 'scene.jpg')))

    def test_allow_real_portrait_at_a_venue(self):
        photos = [
            ('演員李銓 銘傳大學活動.jpg', '演員李銓出席校園活動'),
            ('Singer Dayuan at Temple.jpg', 'Portrait of singer Dayuan'),
            ('張達明.jpg', '張達明接受訪問'),
            ('Huang Shao-gu.jpg', '黃少谷演唱會照片（攝於台北三創五樓）'),
            ('鄭弘儀.jpg', '主持人鄭弘儀接受專訪'),
        ]
        for filename, caption in photos:
            with self.subTest(filename=filename):
                self.assertFalse(obvious_nonportrait_scene(
                    candidate(filename, caption, 'portrait.jpg')))

    def test_scene_does_not_consume_download_quota_or_hide_next_portrait(self):
        class Provider:
            name = 'commons'
            def search(self, person, http, round_number=0):
                yield candidate('Dayuan District 201506.jpg',
                                'Dayuan District', 'dayuan-district.jpg')
                yield candidate('Lin Dayuan singer portrait.jpg',
                                '歌手大元接受專訪', 'lin-dayuan-portrait.jpg')

        class HTTP:
            budget = None
            def __init__(self):
                self.downloads = []
            def get(self, url):
                self.downloads.append(url)
                return b'fixture original bytes'

        def crop(blob):
            return b'fixture cropped jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1]}, {'size': [600, 720]}

        row = {'personId': 't1500_0475', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process({'name': '大元', 'aliases': ['Dayuan'],
                     'acceptedAnswers': ['大元']},
                    row, root, root / 'expansion-1500' / 'pipeline',
                    [Provider()], http, crop, set(), max_candidates=1,
                    max_attempts=2, active={}, rejected_pixels=[])
        self.assertEqual(len(http.downloads), 1)
        self.assertIn('lin-dayuan-portrait.jpg', http.downloads[0])
        self.assertEqual([c['filename'] for c in row['candidates']
                          if c.get('status') == 'pending_review'],
                         ['Lin Dayuan singer portrait.jpg'])
        self.assertIn('nonportrait_scene',
                      [e['code'] for e in row['lastErrors']])


if __name__ == '__main__':
    unittest.main()
