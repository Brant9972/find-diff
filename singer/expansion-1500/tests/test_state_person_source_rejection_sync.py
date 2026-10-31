"""Person-specific human photo rejections must invalidate stale state crops."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from media_pipeline.core import apply_rejections


WRONG = 'https://commons.wikimedia.org/wiki/File:Tzu-Wei_Lin_in_2017_(36962867110).jpg'


def row(pid, status='pending_review'):
    return {'personId': pid, 'status': status, 'nextRetryAt': None,
            'lastRunNewCandidateIds': ['crop'],
            'candidates': [{'id': 'crop', 'source': WRONG,
                            'status': 'pending_review', 'eligibleForLive': False,
                            'gameSha256': 'unchanged-pixels', 'gamePath': 'immutable.jpg'}]}


class PersonSpecificRejectionSyncTest(unittest.TestCase):
    def test_stale_wrong_person_crop_is_rejected_before_export(self):
        state = {'people': {'actor': row('actor'), 'other': row('other')}}
        original = copy.deepcopy(state['people']['actor']['candidates'][0])
        apply_rejections(state, set(), {'actor': [WRONG]})
        actor = state['people']['actor']
        other = state['people']['other']
        self.assertEqual(actor['status'], 'rejected')
        self.assertEqual(actor['lastRunNewCandidateIds'], [])
        self.assertEqual(actor['candidates'][0]['status'], 'rejected')
        self.assertFalse(actor['candidates'][0]['eligibleForLive'])
        self.assertEqual(actor['candidates'][0]['gameSha256'], original['gameSha256'])
        self.assertEqual(actor['candidates'][0]['gamePath'], original['gamePath'])
        self.assertEqual(other['status'], 'pending_review')
        self.assertEqual(other['candidates'][0]['status'], 'pending_review')
        before = copy.deepcopy(state)
        apply_rejections(state, set(), {'actor': [WRONG]})
        self.assertEqual(state, before)

    def test_global_rejection_and_published_guard_still_work(self):
        state = {'people': {'actor': row('actor'), 'published': row('published', 'published')}}
        apply_rejections(state, {'wikimedia:tzu-wei lin in 2017 (36962867110).jpg'})
        self.assertEqual(state['people']['actor']['candidates'][0]['status'], 'rejected')
        self.assertEqual(state['people']['published']['status'], 'published')
        self.assertEqual(state['people']['published']['candidates'][0]['status'], 'pending_review')


if __name__ == '__main__':
    unittest.main()
