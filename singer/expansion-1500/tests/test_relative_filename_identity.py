"""Do not mistake a relative's portrait for the named parent.

A Commons filename can include the parent's exact name while its grammatical
subject is the daughter/son/spouse. The name match is not photo identity.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process


class RelativeFilenameIdentityTest(unittest.TestCase):
    def run_case(self, first_filename, first_caption, p18=False):
        class Provider:
            name = 'commons'

            def search(self, person, http, round_number=0):
                for filename, caption, evidence in [
                    (first_filename, first_caption,
                     {'wikidataId': 'Q123456', 'claim': 'P18'} if p18 else {}),
                    ('黃日華正面肖像.jpg', '演員黃日華接受專訪', {}),
                ]:
                    yield {
                        'provider': 'commons',
                        'source': 'https://commons.wikimedia.org/wiki/File:' + filename,
                        'url': 'https://upload.wikimedia.org/' + filename,
                        'filename': filename, 'caption': caption,
                        'artist': 'Fixture photographer',
                        'license': 'CC BY 4.0',
                        'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                        'identityEvidence': evidence,
                    }

        class HTTP:
            budget = None

            def __init__(self):
                self.downloads = []

            def get(self, url):
                self.downloads.append(url)
                return b'fixture image bytes'

        def crop(blob):
            return b'fixture cropped jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1],
            }, {'size': [600, 720]}

        row = {'personId': 't1500_0554', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process({'name': '黃日華', 'acceptedAnswers': ['黃日華']},
                    row, root, root / 'expansion-1500' / 'pipeline',
                    [Provider()], http, crop, set(), max_candidates=1,
                    active={}, rejected_pixels=[])
        return row, http.downloads

    def test_filename_relative_name_does_not_consume_download_slot(self):
        row, downloads = self.run_case(
            '黃日華的女兒黃芷晴.jpg', '香港女藝人黃芷晴肖像')
        self.assertEqual(downloads,
                         ['https://upload.wikimedia.org/黃日華正面肖像.jpg'])
        self.assertEqual(
            [c['filename'] for c in row['candidates']
             if c['status'] == 'pending_review'],
            ['黃日華正面肖像.jpg'])
        self.assertIn('identity_context_only',
                      [e['code'] for e in row['lastErrors']])

    def test_caption_relative_even_if_filename_names_parent(self):
        row, downloads = self.run_case(
            '黃日華.jpg', '黃日華的女兒黃芷晴接受訪問')
        self.assertEqual(downloads,
                         ['https://upload.wikimedia.org/黃日華正面肖像.jpg'])
        self.assertIn('identity_context_only',
                      [e['code'] for e in row['lastErrors']])

    def test_exact_p18_remains_downloadable_but_never_approved(self):
        row, downloads = self.run_case(
            '黃日華的女兒黃芷晴.jpg', '黃日華的女兒黃芷晴', p18=True)
        self.assertEqual(downloads,
                         ['https://upload.wikimedia.org/黃日華的女兒黃芷晴.jpg'])
        ready = [c for c in row['candidates']
                 if c['status'] == 'pending_review']
        self.assertEqual(len(ready), 1)
        self.assertFalse(ready[0]['eligibleForLive'])
        self.assertIsNone(ready[0]['humanReview'])


if __name__ == '__main__':
    unittest.main()
