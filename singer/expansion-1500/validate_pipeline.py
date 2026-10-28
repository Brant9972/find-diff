#!/usr/bin/env python3
"""Validate saved review outputs without touching production assets."""
import hashlib
from pathlib import Path
from PIL import Image
from media_pipeline.core import STATUSES, contained, read, valid_reveal


def validate(root):
    directory = root / 'expansion-1500/pipeline'
    state = read(directory / 'state.json')
    assert state['schemaVersion'] == 2
    photos = 0
    for pid, person in state['people'].items():
        assert person['personId'] == pid and person['status'] in STATUSES, pid
        assert len({c['id'] for c in person['candidates']}) == len(person['candidates']), pid
        assert sum(c['status'] == 'pending_review' for c in person['candidates']) <= 3, pid
        for candidate in person['candidates']:
            assert candidate.get('eligibleForLive') is False, candidate['id']
            if not candidate.get('gamePath'):
                assert candidate.get('status') in {'metadata_only', 'rejected'}
                continue
            path = contained(root, candidate['gamePath'])
            assert path.is_file(), path
            assert hashlib.sha256(path.read_bytes()).hexdigest() == candidate['gameSha256'], path
            with Image.open(path) as image:
                image.load()
                assert image.size == (600, 720), path
            assert valid_reveal(candidate['reveal']), path
            if candidate.get('originalPath'):
                raw = contained(root, candidate['originalPath'])
                assert hashlib.sha256(raw.read_bytes()).hexdigest() == candidate['originalSha256']
                with Image.open(raw) as image:
                    image.verify()
            if candidate.get('status') == 'approved':
                assert candidate.get('humanReview', {}).get('reviewer'), candidate['id']
            photos += 1
    print(f'PASS: {len(state["people"])} people, {photos} saved photo candidates, hashes, dimensions, reveal boundaries, review-only gate')


if __name__ == '__main__':
    validate(Path(__file__).resolve().parents[1])
