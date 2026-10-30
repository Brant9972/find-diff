"""A curated retry must explain already rejected/retained sources, not redownload."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import process
from media_pipeline.sources import CuratedCommons, source_key


class CuratedNoopGuardTest(unittest.TestCase):
    def test_rejected_and_retained_commons_sources_are_not_downloaded(self):
        file1 = 'Eric Kot 20231029.jpg'
        file2 = 'Eric Kot 200812.JPG'
        source1 = 'https://commons.wikimedia.org/wiki/File:Eric_Kot_20231029.jpg'
        source2 = 'https://commons.wikimedia.org/wiki/File:Eric_Kot_200812.JPG'
        def item(filename, source, original, license_name, license_url):
            return {
                'filename': filename, 'source': source, 'url': original,
                'caption': '葛民輝 Eric Kot at a film event',
                'artist': 'Verified Commons uploader', 'license': license_name,
                'licenseUrl': license_url, 'sourceType': 'uploader_own_work',
                'verificationUrl': source, 'verifiedAt': '2026-10-30',
            }
        person = {
            'name': '葛民輝', 'aliases': ['Eric Kot'],
            'acceptedAnswers': ['葛民輝', 'Eric Kot'],
            'reviewExactCommonsFiles': [file1, file2],
            'reviewVerifiedOriginalSources': [
                item(file1, source1,
                     'https://upload.wikimedia.org/wikipedia/commons/6/63/Eric_Kot_20231029.jpg',
                     'CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/'),
                item(file2, source2,
                     'https://upload.wikimedia.org/wikipedia/commons/3/33/Eric_Kot_200812.JPG',
                     'CC BY 2.5', 'https://creativecommons.org/licenses/by/2.5/'),
            ],
        }
        row = {
            'personId': 't1500_0564', 'name': '葛民輝',
            'status': 'no_suitable_source', 'attempts': 9,
            'candidates': [
                {'id': 'legacy', 'source': source1, 'status': 'rejected'},
                {'id': 'retained', 'source': source2, 'status': 'manual_crop_required'},
            ],
            'history': [],
        }
        self.assertEqual(len(list(CuratedCommons().search(person, None))), 2)

        class NeverDownload:
            budget = None
            def get(self, url):
                raise AssertionError('No retained or rejected source may be downloaded: ' + url)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process(person, row, root, root / 'expansion-1500' / 'pipeline',
                    [CuratedCommons()], NeverDownload(),
                    lambda blob: (_ for _ in ()).throw(AssertionError('Crop should not run')),
                    {source_key(source1)}, active={}, rejected_pixels=[])
        self.assertEqual(row['status'], 'no_suitable_source')
        self.assertEqual(len(row['candidates']), 2)
        self.assertEqual({e['code'] for e in row['lastErrors']},
                         {'curated_already_rejected', 'curated_already_retained'})


if __name__ == '__main__':
    unittest.main()
