"""Explicit photo batches must distinguish skipped people from searched people."""
import copy
import datetime
import unittest

from prepare_media import requested_selection_audit, select_people
from media_pipeline.batch import SEARCH_REVISION


class RequestedSelectionAuditTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime.datetime(2026, 10, 31, 0, 0,
                                     tzinfo=datetime.timezone.utc)
        future = (self.now + datetime.timedelta(hours=4)).isoformat()
        self.state = {'people': {
            'ready': {'status': 'no_suitable_source', 'attempts': 0},
            'cooldown': {'status': 'download_failed', 'attempts': 1,
                         'lastSearchRevision': SEARCH_REVISION,
                         'nextRetryAt': future},
            'published': {'status': 'published', 'attempts': 1},
            'pending': {'status': 'pending_review', 'attempts': 1},
            'duplicate': {'status': 'duplicate_existing', 'attempts': 1},
        }}
        self.people = {pid: {'priority': 'A'} for pid in self.state['people']}
        self.requested = list(self.state['people'])

    def test_explicit_targets_have_separate_selected_and_skipped_counts(self):
        selected = select_people(self.state, self.people, {}, 10,
                                 person_ids=self.requested)
        # The actual selector uses wall-clock time, so the test's cooldown
        # timestamp must be in the future relative to the running test.
        # Verify diagnostics against an explicit selected list instead.
        skipped = requested_selection_audit(
            self.state, self.requested, ['ready'],
            current_time=self.now)
        self.assertEqual(len(skipped), 4)
        self.assertEqual({row['personId']: row['reason'] for row in skipped}, {
            'cooldown': 'cooldown',
            'published': 'already_staged_or_published',
            'pending': 'already_staged_or_published',
            'duplicate': 'already_staged_or_published',
        })
        self.assertEqual(len(self.requested), 1 + len(skipped))
        self.assertIn('ready', selected)
        self.assertEqual(self.state['people']['cooldown']['status'],
                         'download_failed')

    def test_retry_flag_changes_only_explanation_not_approval(self):
        original = copy.deepcopy(self.state)
        skipped = requested_selection_audit(
            self.state, ['published', 'cooldown'], [],
            retry_failed=True, current_time=self.now)
        self.assertEqual(skipped[0]['reason'], 'already_staged_or_published')
        self.assertEqual(skipped[1]['reason'], 'other_selection_filter')
        self.assertEqual(self.state, original)

    def test_unknown_and_malformed_retry_are_reported_not_crashed(self):
        self.state['people']['cooldown']['nextRetryAt'] = 'invalid'
        skipped = requested_selection_audit(
            self.state, ['unknown', 'cooldown'], [],
            current_time=self.now)
        self.assertEqual([row['reason'] for row in skipped],
                         ['unknown_person', 'invalid_retry_timestamp'])


if __name__ == '__main__':
    unittest.main()
