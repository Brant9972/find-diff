"""Prevent already-published people and duplicate IDs from consuming a photo batch."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BatchRequestIntegrityTest(unittest.TestCase):
    def test_explicit_request_is_unique_selected_and_unpublished(self):
        request = json.loads((ROOT / 'pipeline/batch-request.json').read_text(encoding='utf-8'))
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        if request.get('mode') == 'manual_recrop':
            spec_path = ROOT / 'pipeline' / Path(request['manualCropRequestPath']).name
            spec = json.loads(spec_path.read_text(encoding='utf-8'))
            self.assertEqual(spec['releaseGate'], 'MANUAL_CROP_STAGING_ONLY_NO_LIVE')
            ids = [item['personId'] for item in spec['items']]
        else:
            ids = request.get('plannedPersonIds', [])
        self.assertEqual(len(ids), request['targetPeople'])
        self.assertEqual(len(ids), len(set(ids)), 'Do not search the same person twice')
        selected = {row['plannedQuestionId']: row for row in plan['selectedNew']}
        published = set(plan['releaseProgress']['publishedNames'])
        for person_id in ids:
            self.assertIn(person_id, selected)
            self.assertNotEqual(selected[person_id].get('photoStatus'), 'published')
            self.assertNotIn(selected[person_id]['name'], published)

    def test_published_progress_matches_plan_flags_and_selected_arithmetic(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        selected = plan['selectedNew']
        published = [row for row in selected if row.get('photoStatus') == 'published']
        self.assertEqual(len(published), plan['releaseProgress']['published'])
        self.assertEqual(len(published), plan['arithmetic']['publishedFromPlan'])
        self.assertEqual({row['name'] for row in published},
                         set(plan['releaseProgress']['publishedNames']))
        duplicates = [row for row in selected if row.get('duplicateExistingCanonicalId')]
        self.assertEqual(len(duplicates), 1)
        remaining = len(selected) - len(published) - len(duplicates)
        self.assertEqual(remaining, plan['arithmetic']['remainingSelectedNovel'])
        self.assertEqual(remaining, plan['releaseProgress']['pendingPhotoAndHintReview'])
        # Known previously-published people must not be searched again even if
        # their old staging flags were stale before this reconciliation.
        for person_id in ('t1500_0255', 't1500_0355', 't1500_0491',
                          't1500_0557', 't1500_0579', 't1500_0596'):
            row = next(p for p in selected if p['plannedQuestionId'] == person_id)
            self.assertEqual(row['photoStatus'], 'published')

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

    def test_curated_chenxiangqi_lead_does_not_imply_release_approval(self):
        plan = json.loads((ROOT / 'release-plan-20261028.json').read_text(encoding='utf-8'))
        row = next(p for p in plan['selectedNew'] if p['plannedQuestionId'] == 't1500_0171')
        self.assertEqual(row['name'], '陳湘琪')
        self.assertEqual(row['representativeWorks'], ['迴光奏鳴曲'])
        self.assertEqual(row['reviewExactCommonsFiles'], [
            'Chen Shiang-chyi (陳湘琪) at the 51st Golden Horse Awards in November 2014.jpg'])
        self.assertEqual(row['photoStatus'], 'not_prepared')
        self.assertFalse(row['imageVerification']['rightsDocumented'])
        self.assertFalse(row['imageVerification']['finalCropReviewed'])



if __name__ == '__main__':
    unittest.main()
