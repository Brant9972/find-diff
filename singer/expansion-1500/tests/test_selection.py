"""Regression coverage for safely resuming bulk work after a strategy change."""
import datetime
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prepare_media import select_people
from media_pipeline.batch import SEARCH_REVISION


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.people = {key: {'priority': 'A'} for key in ('live', 'approved', 'waiting', 'ready', 'duplicate', 'reviewed', 'fresh', 'old', 'cooldown')}
        self.state = {'people': {key: {'personId': key, 'status': 'no_suitable_source', 'attempts': 0} for key in self.people}}
        for key, status in [('live', 'published'), ('approved', 'approved'), ('waiting', 'pending_review'), ('ready', 'candidate_ready'), ('duplicate', 'duplicate_existing')]:
            self.state['people'][key]['status'] = status
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
        for key, revision in [('old', SEARCH_REVISION - 1), ('cooldown', SEARCH_REVISION)]:
            self.state['people'][key].update(nextRetryAt=future, lastSearchRevision=revision, attempts=2)
        self.state['people']['reviewed']['attempts'] = 3
        self.handoff = {'personIds': ['reviewed', 'waiting']}

    def test_skip_live_approved_and_pending_preserve_cooldown(self):
        selected = select_people(self.state, self.people, self.handoff, 40)
        self.assertEqual(selected, ['reviewed', 'fresh', 'old'])

    def test_retry_failed_is_explicit_and_still_protects_approved_pending(self):
        selected = select_people(self.state, self.people, self.handoff, 40, retry_failed=True)
        self.assertEqual(set(selected), {'reviewed', 'fresh', 'old', 'cooldown'})

    def test_legacy_review_scope_and_explicit_id_filter(self):
        self.assertEqual(select_people(self.state, self.people, self.handoff, 40, review_only=True), ['reviewed'])
        self.assertEqual(select_people(self.state, self.people, self.handoff, 40, person_ids=['old']), ['old'])

    def test_curated_exact_commons_hints_remain_draft_only(self):
        plan_path = Path(__file__).resolve().parents[1] / 'release-plan-20261028.json'
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        row = next(person for person in plan['selectedNew']
                   if person['plannedQuestionId'] == 't1500_0107')
        self.assertEqual(row['name'], '陳明章')
        self.assertEqual(row['wikidataId'], 'Q9474720')
        self.assertEqual(len(row['reviewExactCommonsFiles']), 3)
        self.assertTrue(all(filename.lower().endswith('.jpg')
                            for filename in row['reviewExactCommonsFiles']))
        self.assertNotEqual(row['photoStatus'], 'published')
        self.assertFalse(row['imageVerification']['finalCropReviewed'])
        self.assertNotEqual(row['qaStatus'], 'releasable')

    def test_musician_huang_shaoku_cannot_use_politician_qid(self):
        plan_path = Path(__file__).resolve().parents[1] / 'release-plan-20261028.json'
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        row = next(person for person in plan['selectedNew']
                   if person['plannedQuestionId'] == 't1500_0108')
        self.assertEqual(row['name'], '黃少谷')
        self.assertEqual(row['wikidataId'], 'Q28408495')
        self.assertIn('黃少谷 20171015誠品唱談會.jpg', row['reviewExactCommonsFiles'])
        self.assertIn('https://commons.wikimedia.org/wiki/File:Huang_Shao-gu.jpg', row['excludedPhotoSources'])
        if row['photoStatus'] == 'published':
            self.assertTrue(row['imageVerification']['finalCropReviewed'])
            self.assertTrue(row['imageVerification']['rightsDocumented'])
            self.assertTrue(row.get('gameSha256'))
        else:
            self.assertFalse(row['imageVerification']['finalCropReviewed'])
            self.assertNotEqual(row['photoStatus'], 'published')

    def test_limit_applies_after_review_priority(self):
        self.assertEqual(select_people(self.state, self.people, self.handoff, 1), ['reviewed'])


if __name__ == '__main__':
    unittest.main()
