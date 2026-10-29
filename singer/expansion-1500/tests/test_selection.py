"""Regression coverage for safely resuming bulk work after a strategy change."""
import datetime
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

    def test_limit_applies_after_review_priority(self):
        self.assertEqual(select_people(self.state, self.people, self.handoff, 1), ['reviewed'])


if __name__ == '__main__':
    unittest.main()
