"""One bounded high-resolution Commons retry can recover tiny/soft preview faces.

This never waives rights, pixel rejection, crop validation or human approval.
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process
from media_pipeline.sources import SourceError

PREVIEW = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Actor.jpg/1400px-Actor.jpg'
ORIGINAL = 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Actor.jpg'


class HighResolutionRetryTest(unittest.TestCase):
    def run_case(self, failure='Blurred crop: sharpness below 65',
                 original=ORIGINAL, width=3200, height=4200,
                 variant='wikimedia_thumbnail_1400', fail_original=False):
        class Provider:
            name = 'commons'
            def search(self, person, http, round_number=0):
                yield {
                    'provider': 'commons',
                    'source': 'https://commons.wikimedia.org/wiki/File:林慶台.jpg',
                    'url': PREVIEW,
                    'originalUrl': original,
                    'downloadVariant': variant,
                    'filename': '林慶台.jpg',
                    'caption': '演員林慶台接受專訪',
                    'artist': 'Fixture photographer',
                    'license': 'CC BY 4.0',
                    'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
                    'width': width, 'height': height,
                    'identityEvidence': {},
                }

        class HTTP:
            budget = None
            def __init__(self):
                self.downloads = []
            def get(self, url):
                self.downloads.append(url)
                if url == original and fail_original:
                    raise SourceError('http_403', 'Fixture denied')
                return b'original pixels' if url == original else b'preview pixels'

        def crop(blob):
            if blob == b'preview pixels':
                raise ValueError(failure)
            return b'game jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1],
            }, {'size': [600, 720], 'sharpness': 100}

        row = {'personId': 't1500_0123', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process({'name': '林慶台', 'acceptedAnswers': ['林慶台']},
                    row, root, root / 'expansion-1500' / 'pipeline',
                    [Provider()], http, crop, set(), active={},
                    max_candidates=1, max_attempts=2, rejected_pixels=[])
        return row, http.downloads

    def test_blurred_preview_uses_licensed_original_and_still_requires_review(self):
        row, downloads = self.run_case()
        self.assertEqual(downloads, [PREVIEW, ORIGINAL])
        candidate = next(c for c in row['candidates']
                         if c['status'] == 'pending_review')
        self.assertEqual(candidate['downloadVariant'],
                         'wikimedia_original_after_crop_failure')
        self.assertEqual(candidate['originalSha256'],
                         hashlib.sha256(b'original pixels').hexdigest())
        self.assertFalse(candidate['eligibleForLive'])
        self.assertIsNone(candidate['humanReview'])

    def test_small_face_preview_can_retry_full_resolution(self):
        row, downloads = self.run_case(failure='Face is too small')
        self.assertEqual(downloads, [PREVIEW, ORIGINAL])
        self.assertEqual(row['status'], 'pending_review')

    def test_untrusted_original_host_never_downloaded(self):
        row, downloads = self.run_case(
            original='https://example.com/unrelated.jpg')
        self.assertEqual(downloads, [PREVIEW])
        self.assertNotEqual(row['status'], 'pending_review')

    def test_same_host_different_commons_file_never_downloaded(self):
        _, downloads = self.run_case(
            original='https://upload.wikimedia.org/wikipedia/commons/b/bc/Other.jpg')
        self.assertEqual(downloads, [PREVIEW])

    def test_no_original_retry_for_geometry_or_overexposure(self):
        for failure in ('Multiple prominent faces',
                        'Overexposed crop: more than 55% near-white pixels'):
            with self.subTest(failure=failure):
                _, downloads = self.run_case(failure=failure)
                self.assertEqual(downloads, [PREVIEW])

    def test_no_retry_for_oversize_or_small_original(self):
        for width, height in ((8000, 6000), (1200, 1400)):
            with self.subTest(dimensions=(width, height)):
                _, downloads = self.run_case(width=width, height=height)
                self.assertEqual(downloads, [PREVIEW])

    def test_original_http_error_preserves_manual_review_without_approval(self):
        row, downloads = self.run_case(fail_original=True)
        self.assertEqual(downloads, [PREVIEW, ORIGINAL])
        self.assertIn('highres_retry_download_failed',
                      [e['code'] for e in row['lastErrors']])
        self.assertFalse(any(c['status'] == 'pending_review'
                             for c in row['candidates']))


if __name__ == '__main__':
    unittest.main()
