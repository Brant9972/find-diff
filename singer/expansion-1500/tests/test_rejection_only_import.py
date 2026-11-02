"""A reviewed rejection must be imported once, never promoted to an approval."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media_pipeline.review import validate_rejection_only_document, import_decisions


class RejectionImportTests(unittest.TestCase):
    def setUp(self):
        self.digest = hashlib.sha256(b'jpeg-fixture').hexdigest()
        self.entry = {'personId': 't1500_0123', 'candidateId': 'manualrecrop-test',
                      'gameSha256': self.digest, 'decision': 'rejected',
                      'reason': 'Eyes reveal points at backdrop, not eyes'}
        self.document = {'schemaVersion': 1, 'reviewer': 'Human visual reviewer',
                         'reviewedAt': '2026-11-02T09:54:24+08:00',
                         'decisions': [dict(self.entry)]}

    def test_only_explicit_rejections_are_accepted(self):
        self.assertEqual(len(validate_rejection_only_document(self.document)), 1)
        for bad in ['approved', 'pending']:
            doc = {**self.document, 'decisions': [{**self.entry, 'decision': bad}]}
            with self.assertRaises(ValueError):
                validate_rejection_only_document(doc)
        with self.assertRaises(ValueError):
            validate_rejection_only_document({**self.document, 'decisions': [self.entry, self.entry]})
        with self.assertRaises(ValueError):
            validate_rejection_only_document({**self.document, 'decisions': [{**self.entry, 'gameSha256': '0'}]})

    def test_hash_bound_import_rejects_photo_without_touching_live(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / 'singer/expansion-1500/pipeline/assets/candidate.jpg'
            game.parent.mkdir(parents=True)
            game.write_bytes(b'jpeg-fixture')
            directory = root / 'singer/expansion-1500/pipeline'
            candidate = {'id': 'manualrecrop-test', 'status': 'pending_review',
                         'gamePath': str(game.relative_to(root)),
                         'gameSha256': self.digest, 'rightsStatus': 'open_license_metadata'}
            person = {'status': 'pending_review', 'candidates': [candidate]}
            state = {'people': {'t1500_0123': person}}
            validate_rejection_only_document(self.document)
            import_decisions(root, directory, state, self.document)
            self.assertEqual(candidate['status'], 'rejected')
            self.assertEqual(person['status'], 'rejected')
            self.assertFalse(candidate['eligibleForLive'])
            self.assertEqual(candidate['humanReview']['gameSha256'], self.digest)
            self.assertEqual(len(list((directory / 'reviews').glob('*.json'))), 1)

    def test_mismatched_actual_bytes_block_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / 'singer/expansion-1500/pipeline/assets/candidate.jpg'
            game.parent.mkdir(parents=True)
            game.write_bytes(b'tampered')
            directory = root / 'singer/expansion-1500/pipeline'
            candidate = {'id': 'manualrecrop-test', 'status': 'pending_review',
                         'gamePath': str(game.relative_to(root)),
                         'gameSha256': self.digest, 'rightsStatus': 'open_license_metadata'}
            state = {'people': {'t1500_0123': {'status': 'pending_review', 'candidates': [candidate]}}}
            with self.assertRaises(ValueError):
                import_decisions(root, directory, state, self.document)
            self.assertEqual(candidate['status'], 'pending_review')
            self.assertFalse((directory / 'reviews').exists())


if __name__ == '__main__':
    unittest.main()
