"""Prior human-rejected Commons hits must explain zero-yield batches."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process
from media_pipeline.sources import source_key


SOURCE = 'https://commons.wikimedia.org/wiki/File:Already_rejected.jpg'


class CommonsFixture:
    name = 'commons'

    def search(self, person, http, round_number=0):
        yield {
            'provider': 'commons',
            'source': SOURCE,
            'url': 'https://upload.wikimedia.org/wikipedia/commons/a/aa/Already_rejected.jpg',
            'filename': 'Already rejected.jpg',
            'caption': 'Already rejected photo',
            'artist': 'Example',
            'license': 'CC BY 4.0',
            'licenseUrl': 'https://creativecommons.org/licenses/by/4.0/',
        }


class NoDownloads:
    budget = None

    def get(self, url):
        raise AssertionError('A rejected source must never be downloaded')


class RejectedSourceDiagnosticsTest(unittest.TestCase):
    def check(self, excluded_by_person, global_rejection):
        person = {'name': '測試藝人', 'excludedPhotoSources': excluded_by_person}
        row = {'personId': 't1500_test', 'name': '測試藝人',
               'status': 'no_suitable_source', 'attempts': 0,
               'candidates': [], 'history': []}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process(person, row, root, root / 'expansion-1500' / 'pipeline',
                    [CommonsFixture()], NoDownloads(),
                    lambda blob: self.fail('No crop of a rejected source'),
                    global_rejection, active={}, rejected_pixels=[])
        self.assertEqual(row['status'], 'no_suitable_source')
        self.assertEqual(row['candidates'], [])
        self.assertEqual(len(row['lastErrors']), 1)
        self.assertEqual(row['lastErrors'][0]['code'], 'source_already_rejected')
        self.assertEqual(row['lastErrors'][0]['source'], SOURCE)
        self.assertFalse(any(c.get('status') == 'pending_review'
                             for c in row['candidates']))

    def test_global_human_rejection_is_reported_not_silently_skipped(self):
        self.check([], {source_key(SOURCE)})

    def test_person_specific_exclusion_is_reported_not_retried(self):
        self.check([SOURCE], set())


if __name__ == '__main__':
    unittest.main()
