"""A CC tag on Commons is not approval while licence review is pending."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process
from media_pipeline.sources import CommonsSearch, commons_review_status, rights


class CommonsLicenseReviewGuardTest(unittest.TestCase):
    def test_hidden_review_categories_override_open_cc_metadata(self):
        self.assertEqual(commons_review_status({
            'categories': [{'title': 'Category:License review needed'}]}), 'needed')
        self.assertEqual(commons_review_status({
            'categories': [{'title': 'Category:License review failed'}]}), 'failed')
        self.assertEqual(commons_review_status({'categories': []}), 'not_flagged')
        self.assertEqual(commons_review_status({}), 'not_checked')
        candidate = {
            'license': 'CC BY 3.0',
            'licenseUrl': 'https://creativecommons.org/licenses/by/3.0/',
            'artist': 'am730',
            'licenseReviewStatus': 'needed',
        }
        self.assertEqual(rights(candidate), 'needs_review')
        candidate['licenseReviewStatus'] = 'failed'
        self.assertEqual(rights(candidate), 'rights_disputed')
        candidate['licenseReviewStatus'] = 'not_flagged'
        self.assertEqual(rights(candidate), 'open_license_metadata')

    def test_commons_flag_survives_adapter_and_prevents_download(self):
        class HTTP:
            budget = None
            verified_identities = {}
            def __init__(self):
                self.downloads = []
                self.calls = []
            def json(self, url, **params):
                self.calls.append(params)
                assert 'categories' in params.get('prop', '')
                assert 'Category:License review needed' in params.get('clcategories', '')
                return {'query': {'pages': [{
                    'title': 'File:向海嵐.jpg',
                    'categories': [{'title': 'Category:License review needed'}],
                    'imageinfo': [{
                        'url': 'https://upload.wikimedia.org/portrait.jpg',
                        'descriptionurl': 'https://commons.wikimedia.org/wiki/File:向海嵐.jpg',
                        'extmetadata': {key: {'value': value} for key, value in {
                            'Artist': 'am730',
                            'LicenseShortName': 'CC BY 3.0',
                            'LicenseUrl': 'https://creativecommons.org/licenses/by/3.0/',
                            'ImageDescription': '香港女演員向海嵐',
                        }.items()},
                    }],
                }]}}
            def get(self, url):
                self.downloads.append(url)
                raise AssertionError('Licence-review-pending media must not be downloaded')

        person = {'name': '向海嵐', 'plannedQuestionId': 't1500_0586'}
        http = HTTP()
        items = list(CommonsSearch().search(person, http))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['licenseReviewStatus'], 'needed')
        self.assertEqual(rights(items[0]), 'needs_review')
        row = {'personId': 't1500_0586', 'status': 'not_started',
               'attempts': 0, 'candidates': [], 'history': []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process(person, row, root, root / 'expansion-1500' / 'pipeline',
                    [CommonsSearch()], http, lambda blob: None, set(),
                    max_candidates=1, max_attempts=2, active={}, rejected_pixels=[])
        self.assertEqual(http.downloads, [])
        self.assertTrue(any(e['code'] == 'license_unclear'
                            for e in row['lastErrors']))
        self.assertTrue(all(c.get('eligibleForLive') is False
                            for c in row['candidates']))


if __name__ == '__main__':
    unittest.main()
