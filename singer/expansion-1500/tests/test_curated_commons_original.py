"""Curated Commons original URLs are a constrained source fallback, not approval."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.sources import CuratedCommons, rights
from media_pipeline.core import process


class CuratedCommonsOriginalTest(unittest.TestCase):
    def setUp(self):
        self.source = 'https://commons.wikimedia.org/wiki/File:Eric_Kot_20231029.jpg'
        self.original = 'https://upload.wikimedia.org/wikipedia/commons/6/63/Eric_Kot_20231029.jpg'
        self.item = {
            'filename': 'Eric Kot 20231029.jpg', 'source': self.source,
            'url': self.original, 'artist': 'Tombus20032000',
            'caption': '葛民輝 at an event, Eric Kot',
            'license': 'CC BY-SA 4.0',
            'licenseUrl': 'https://creativecommons.org/licenses/by-sa/4.0/',
            'sourceType': 'uploader_own_work',
            'verificationUrl': self.source, 'verifiedAt': '2026-10-30',
        }
        self.person = {
            'name': '葛民輝', 'aliases': ['Eric Kot'],
            'acceptedAnswers': ['葛民輝', 'Eric Kot'],
            'reviewExactCommonsFiles': ['Eric Kot 20231029.jpg'],
            'reviewVerifiedOriginalSources': [self.item],
        }

    def test_only_strict_wikimedia_originals_and_own_work_metadata(self):
        rows = list(CuratedCommons().search(self.person, None))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], self.original)
        self.assertEqual(rights(rows[0]), 'open_license_metadata')
        self.assertFalse(rows[0]['identityEvidence']['visualIdentityVerified'])
        for change in [
            {'url': 'https://example.com/Eric_Kot_20231029.jpg'},
            {'url': 'https://upload.wikimedia.org/wikipedia/commons/6/63/other.jpg'},
            {'source': 'https://example.com/wiki/File:Eric_Kot_20231029.jpg'},
            {'artist': ''},
            {'sourceType': 'unknown'},
            {'verificationUrl': 'https://example.com'},
            {'license': 'All rights reserved'},
            {'caption': 'Unknown person'},
        ]:
            with self.subTest(change=change):
                bad = {**self.item, **change}
                self.assertEqual(list(CuratedCommons().search(
                    {**self.person, 'reviewVerifiedOriginalSources': [bad]}, None)), [])

    def test_hashed_wikimedia_thumbnails_are_review_only_and_strict(self):
        thumbnail = ('https://upload.wikimedia.org/wikipedia/commons/thumb/'
                     '6/63/Eric_Kot_20231029.jpg/960px-Eric_Kot_20231029.jpg')
        item = {**self.item, 'url': thumbnail}
        rows = list(CuratedCommons().search(
            {**self.person, 'reviewVerifiedOriginalSources': [item]}, None))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['url'], thumbnail)
        self.assertEqual(rows[0]['originalUrl'], self.original)
        self.assertEqual(rows[0]['downloadVariant'], 'wikimedia_thumbnail_curated')
        self.assertFalse(rows[0]['identityEvidence']['visualIdentityVerified'])
        for bad_url in [
            thumbnail.replace('/6/63/', '/6/62/'),
            thumbnail.replace('960px-', '999px-'),
            thumbnail.replace('Eric_Kot_20231029.jpg/960px-', 'Other.jpg/960px-'),
            thumbnail + '?cache=1',
            thumbnail.replace('upload.wikimedia.org', 'example.com'),
        ]:
            with self.subTest(url=bad_url):
                bad = {**item, 'url': bad_url}
                self.assertEqual(list(CuratedCommons().search(
                    {**self.person, 'reviewVerifiedOriginalSources': [bad]}, None)), [])

    def test_backup_photo_leads_are_not_human_approved(self):
        import json
        root = Path(__file__).resolve().parents[1]
        leads = json.loads((root / 'pipeline/backup-photo-leads-20261030.json')
                           .read_text(encoding='utf-8'))
        backup = leads['people'][0]
        self.assertEqual(backup['plannedQuestionId'], 't1500_0604')
        person = {
            'name': backup['name'], 'aliases': [], 'acceptedAnswers': [backup['name']],
            'reviewExactCommonsFiles': backup['reviewExactCommonsFiles'],
            'reviewVerifiedOriginalSources': backup['reviewVerifiedOriginalSources'],
        }
        rows = list(CuratedCommons().search(person, None))
        self.assertEqual(rows, [], 'Unreachable Commons URLs must not be retried as curated leads')
        self.assertEqual(backup['reviewStatus'], 'SOURCE_UNAVAILABLE_HTTP_404_NOT_APPROVED')
        self.assertEqual(len(backup['unavailableThumbnailLeads']), 2)
        self.assertEqual(backup['availabilityReview']['result'],
                         'BOTH_THUMBNAILS_HTTP_404_AND_COMMONS_PAGE_NOT_ACCESSIBLE')

    def test_replaces_same_source_metadata_even_if_url_variant_changes(self):
        old_url = self.original + '?utm_source=commons'
        old = {**self.item, 'url': old_url, 'status': 'metadata_only',
               'id': hashlib.sha256(('t1500_0564\n' + self.source + '\n' + old_url)
                                    .encode()).hexdigest()[:20]}
        row = {'personId': 't1500_0564', 'status': 'no_suitable_source',
               'attempts': 0, 'candidates': [old], 'history': []}

        class HTTP:
            budget = None
            def __init__(self):
                self.downloads = []
            def get(self, url):
                self.downloads.append(url)
                return b'original jpeg fixture'

        def crop(blob):
            return b'cropped jpeg fixture', {
                'eyes': [0, 0, 1, .2], 'nose': [0, 0, 1, .4],
                'mouth': [0, 0, 1, .6], 'chin': [0, 0, 1, .8],
                'full': [0, 0, 1, 1]}, {'size': [600, 720]}

        http = HTTP()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process(self.person, row, root,
                    root / 'expansion-1500' / 'pipeline',
                    [CuratedCommons()], http, crop, set(), max_candidates=1,
                    max_attempts=2, active={}, rejected_pixels=[])
        self.assertEqual(http.downloads, [self.original])
        candidates = [c for c in row['candidates']
                      if c.get('source') == self.source]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['status'], 'pending_review')
        self.assertFalse(candidates[0]['eligibleForLive'])


if __name__ == '__main__':
    unittest.main()
