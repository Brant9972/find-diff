"""Prevent already-published people and duplicate IDs from consuming a photo batch."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BatchRequestIntegrityTest(unittest.TestCase):
    def test_explicit_request_is_unique_selected_and_unpublished(self):
        request = json.loads((ROOT / 'pipeline/batch-request.json').read_text(encoding='utf-8'))
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        ids = request.get('plannedPersonIds', [])
        self.assertEqual(len(ids), request['targetPeople'])
        self.assertEqual(len(ids), len(set(ids)), 'Do not search the same person twice')
        selected = {row['plannedQuestionId']: row for row in plan['selectedNew']}
        published = set(plan['releaseProgress']['publishedNames'])
        for person_id in ids:
            self.assertIn(person_id, selected)
            self.assertNotEqual(selected[person_id].get('photoStatus'), 'published')
            self.assertNotIn(selected[person_id]['name'], published)

    def test_exact_commons_leads_remain_bounded_metadata_only(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        for row in plan['selectedNew']:
            files = row.get('reviewExactCommonsFiles', [])
            self.assertLessEqual(len(files), 3)
            for filename in files:
                self.assertNotIn('/', filename)
                self.assertNotIn('\\\\', filename)
                self.assertTrue(filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')))
            # A curated filename is only a source hint, never approval.
            if files and row.get('photoStatus') != 'published':
                self.assertNotEqual(row.get('qaStatus'), 'Pages_live_verified')


if __name__ == '__main__':
    unittest.main()
