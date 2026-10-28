import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import atomic
from media_pipeline.handoff import consume


class HandoffRoundsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'singer'
        self.directory = self.root / 'expansion-1500/pipeline'
        self.state = {'schemaVersion': 2, 'people': {}}
        self.document = {'schemaVersion': 1, 'releaseGate': 'DRAFT_ONLY_NOT_PLAYABLE',
                         'sourceCommit': 'photo-source-commit', 'sourceRun': 'source-run',
                         'decisions': [], 'newCandidates': []}

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, pid, cid, color='#a78568'):
        path = self.root / ('expansion-1500/review_photos/' + cid + '.jpg')
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (600, 720), color).save(path)
        candidate = {'id': cid, 'gamePath': str(path.relative_to(self.root)),
                     'gameSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'status': 'pending_review', 'eligibleForLive': False}
        row = self.state['people'].setdefault(pid, {'personId': pid, 'name': pid,
            'status': 'pending_review', 'attempts': 0, 'candidates': [], 'nextRetryAt': None})
        row['candidates'].append(candidate)
        return candidate

    def decision(self, pid, candidate, decision='pending', reason='Review source and pixels'):
        return {'personId': pid, 'candidateId': candidate['id'], 'gameSha256': candidate['gameSha256'],
                'decision': decision, 'reason': reason, 'eligibleForLive': False}

    def write(self):
        atomic(self.directory / 'chatgpt-review/latest.json', self.document)

    def apply(self):
        self.write()
        return consume(self.root, self.directory, self.state)

    def test_eighteen_people_nineteen_candidates_preserve_six_pending_people(self):
        for n in range(18):
            pid = 'person' + str(n)
            candidate = self.candidate(pid, 'legacy-' + pid)
            decision = 'pending' if n < 6 else 'reject'
            self.document['decisions'].append(self.decision(pid, candidate, decision))
        extra = self.candidate('person0', 'source-recrop-person0', '#4f7361')
        self.document['newCandidates'].append(self.decision('person0', extra))
        result = self.apply()
        self.assertEqual(len(result['personIds']), 18)
        self.assertEqual(len(set(result['personIds'])), 18)
        self.assertEqual(len(result['candidateRefs']), 19)
        self.assertEqual(result['counts'], {'reject': 12, 'pending': 7})
        self.assertEqual(result['peopleCounts'], {'reviewed': 18, 'pending': 6, 'reject': 12})
        self.assertEqual(len(self.state['people']['person0']['chatgptReviews']), 2)
        self.assertEqual(self.state['people']['person0']['chatgptReview']['candidateId'], 'legacy-person0')
        self.assertEqual(extra['status'], 'pending_evidence')
        self.assertFalse(extra['eligibleForLive'])

    def test_old_photo_rejection_cannot_erase_new_candidate_pending_state(self):
        old = self.candidate('p1', 'old')
        new = self.candidate('p1', 'new', '#283a56')
        self.document['decisions'] = [self.decision('p1', old, 'reject', 'Background face')]
        self.document['newCandidates'] = [self.decision('p1', new)]
        self.apply()
        self.assertEqual(old['status'], 'rejected')
        self.assertEqual(new['status'], 'pending_evidence')
        self.assertEqual(self.state['people']['p1']['status'], 'pending_review')
        self.assertEqual(self.state['people']['p1']['chatgptReview']['candidateId'], 'old')
        self.assertEqual(self.state['people']['p1']['chatgptReviews']['new']['decision'], 'pending')

    def test_metadata_only_sha_update_preserves_search_progress_and_cooldown(self):
        old = self.candidate('p1', 'old')
        self.document['decisions'] = [self.decision('p1', old, 'reject')]
        self.apply()
        row = self.state['people']['p1']
        row.update({'status': 'download_failed', 'attempts': 5, 'nextRetryAt': '2030-01-01T00:00:00Z',
                    'lastErrors': [{'code': 'http_403', 'message': 'source refused'}]})
        prior_history = copy.deepcopy(old['externalReviewHistory'])
        old_digest = self.state['chatgptReview']['sha256']
        self.document['latestEvidenceCommit'] = 'evidence-metadata-only-change'
        self.document['decisions'][0]['evidenceStatus'] = 'visual_not_verified'
        result = self.apply()
        self.assertNotEqual(result['sha256'], old_digest)
        self.assertEqual(result['changedCandidates'], 0)
        self.assertEqual(row['status'], 'download_failed')
        self.assertEqual(row['attempts'], 5)
        self.assertEqual(row['nextRetryAt'], '2030-01-01T00:00:00Z')
        self.assertEqual(row['lastErrors'][0]['code'], 'http_403')
        self.assertEqual(old['externalReviewHistory'], prior_history)
        self.assertEqual(row['chatgptReviews']['old']['sourceReviewSha256'], result['sha256'])

    def test_adding_new_candidate_does_not_restart_previous_rejected_person(self):
        rejected = self.candidate('p1', 'rejected')
        pending = self.candidate('p2', 'pending')
        self.document['decisions'] = [self.decision('p1', rejected, 'reject'), self.decision('p2', pending)]
        self.apply()
        row = self.state['people']['p1']
        row.update({'status': 'download_failed', 'nextRetryAt': '2030-01-01T00:00:00Z', 'attempts': 3})
        new = self.candidate('p2', 'new-pending', '#273727')
        self.document['newCandidates'] = [self.decision('p2', new)]
        result = self.apply()
        self.assertEqual(result['changedCandidates'], 1)
        self.assertEqual(row['status'], 'download_failed')
        self.assertEqual(row['nextRetryAt'], '2030-01-01T00:00:00Z')
        self.assertEqual(len(rejected['externalReviewHistory']), 1)
        self.assertEqual(new['status'], 'pending_evidence')

    def test_stale_new_candidate_rejects_entire_handoff_without_archive(self):
        old = self.candidate('p1', 'old')
        new = self.candidate('p1', 'new')
        self.document['decisions'] = [self.decision('p1', old, 'reject')]
        stale = self.decision('p1', new)
        stale['gameSha256'] = 'stale'
        self.document['newCandidates'] = [stale]
        before = copy.deepcopy(self.state)
        self.write()
        with self.assertRaisesRegex(ValueError, 'Stale'):
            consume(self.root, self.directory, self.state)
        self.assertEqual(self.state, before)
        self.assertFalse((self.directory / 'chatgpt-review/received').exists())

    def test_duplicate_across_collections_is_atomic(self):
        candidate = self.candidate('p1', 'old')
        decision = self.decision('p1', candidate)
        self.document['decisions'] = [decision]
        self.document['newCandidates'] = [copy.deepcopy(decision)]
        before = copy.deepcopy(self.state)
        self.write()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            consume(self.root, self.directory, self.state)
        self.assertEqual(self.state, before)

    def test_unchanged_json_still_validates_current_image_bytes(self):
        candidate = self.candidate('p1', 'old')
        self.document['decisions'] = [self.decision('p1', candidate)]
        self.apply()
        before = copy.deepcopy(self.state)
        (self.root / candidate['gamePath']).write_bytes(b'changed image bytes')
        with self.assertRaisesRegex(ValueError, 'Stale'):
            consume(self.root, self.directory, self.state)
        self.assertEqual(self.state, before)

    def test_new_preliminary_decision_cannot_change_protected_candidate(self):
        candidate = self.candidate('p1', 'old')
        self.document['decisions'] = [self.decision('p1', candidate)]
        self.apply()
        self.state['people']['p1']['status'] = 'published'
        before = copy.deepcopy(self.state)
        self.document['decisions'][0]['decision'] = 'reject'
        self.write()
        with self.assertRaisesRegex(ValueError, 'approved/published'):
            consume(self.root, self.directory, self.state)
        self.assertEqual(self.state, before)


if __name__ == '__main__':
    unittest.main()
