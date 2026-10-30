"""A verified alias correction can recheck cached exact-source metadata offline."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process


class CachedExactMetadataReplayTest(unittest.TestCase):
    def test_one_shot_replay_downloads_only_curated_source_and_no_duplicates(self):
        source = 'https://commons.wikimedia.org/wiki/File:Eric_Kot_20231029.jpg'
        url = 'https://upload.wikimedia.org/wikipedia/commons/6/63/Eric_Kot_20231029.jpg'
        person_id = 't1500_0564'
        cid = hashlib.sha256((person_id + '\n' + source + '\n' + url).encode()
                             ).hexdigest()[:20]
        cached = {
            'id': cid, 'personId': person_id, 'status': 'metadata_only',
            'source': source, 'url': url, 'filename': 'Eric Kot 20231029.jpg',
            'provider': 'commons', 'caption': 'Eric Kot in 2023',
            'artist': 'Tombus20032000', 'license': 'CC BY-SA 4.0',
            'licenseUrl': 'https://creativecommons.org/licenses/by-sa/4.0/',
            'rightsStatus': 'open_license_metadata',
            'identityEvidence': {'identityWarning': 'Metadata is not approval'},
        }
        other = {**cached, 'id': 'other',
                 'source': 'https://commons.wikimedia.org/wiki/File:Unrelated.jpg',
                 'filename': 'Unrelated.jpg'}
        row = {'personId': person_id, 'status': 'no_suitable_source',
               'attempts': 2, 'candidates': [cached, other], 'history': []}
        person = {'name': '葛民輝', 'aliases': ['Eric Kot'],
                  'acceptedAnswers': ['葛民輝', 'Eric Kot'],
                  'reviewExactCommonsFiles': ['Eric Kot 20231029.jpg'],
                  'cachedMetadataRecheckToken': '20261030-verified-english-alias'}

        class HTTP:
            budget = None
            def __init__(self):
                self.downloads = []
            def get(self, value):
                self.downloads.append(value)
                return b'original fixture bytes'

        def crop(blob):
            return b'cropped fixture jpeg', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1]}, {'size': [600, 720]}

        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = (person, row, root, root / 'expansion-1500' / 'pipeline',
                    [], http, crop, set())
            process(*args, max_candidates=1, max_attempts=3,
                    active={}, rejected_pixels=[])
            self.assertEqual(row['lastCachedRecheckToken'],
                             '20261030-verified-english-alias')
            self.assertEqual(http.downloads, [url])
            matches = [c for c in row['candidates']
                       if c.get('source') == source]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]['status'], 'pending_review')
            self.assertEqual(other['status'], 'metadata_only')
            process(*args, max_candidates=1, max_attempts=3,
                    active={}, rejected_pixels=[])
        self.assertEqual(http.downloads, [url])
        self.assertEqual(len([c for c in row['candidates']
                              if c.get('source') == source]), 1)


if __name__ == '__main__':
    unittest.main()
