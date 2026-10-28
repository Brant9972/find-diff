#!/usr/bin/env python3
"""Recover our review artifact only against an unchanged expected state checkpoint."""
import hashlib
import sys
from pathlib import Path
from media_pipeline.core import atomic, immutable_bytes, read
from media_pipeline.sources import now


def recover(root, artifact_root):
    directory = root / 'expansion-1500/pipeline'
    request_path = directory / 'recovery-request.json'
    request = read(request_path)
    if not request or request.get('completed'):
        return
    actual = hashlib.sha256((directory / 'state.json').read_bytes()).hexdigest()
    matches = [p for p in artifact_root.rglob('pipeline') if p.is_dir() and (p / 'state.json').exists()]
    if len(matches) != 1:
        raise ValueError('Artifact must contain exactly one pipeline state')
    source = matches[0]
    current, incoming = read(directory / 'state.json'), read(source / 'state.json')
    if actual != request['baseStateSha256'] and current != incoming:
        raise ValueError('Local state changed since recovery was requested; refusing overwrite')
    if incoming.get('schemaVersion') != 2 or set(current['people']) != set(incoming['people']):
        raise ValueError('Recovery schema/people differ')
    for pid, row in incoming['people'].items():
        prior = current['people'][pid]
        if prior['status'] in {'approved', 'published'} and prior != row:
            raise ValueError('Recovery would change approved/published person')
        if row['status'] == 'approved' and prior['status'] != 'approved':
            raise ValueError('A collection artifact cannot introduce approval')
        old_reviews = {c['id']: c.get('humanReview') for c in prior['candidates']}
        for candidate in row['candidates']:
            if candidate.get('humanReview') != old_reviews.get(candidate['id']):
                raise ValueError('A collection artifact cannot introduce/change human review')
    files = [p for p in source.rglob('*') if p.is_file()]
    for path in source.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlinks are not allowed in recovery artifacts')
    for path in files:
        relative = path.relative_to(source)
        if relative.parts[0] not in {'assets', 'runs', 'state.json', 'latest.json'}:
            raise ValueError('Unexpected recovery file: ' + str(relative))
        target = directory / relative
        if relative.parts[0] in {'assets', 'runs'} and target.exists() and target.read_bytes() != path.read_bytes():
            raise ValueError('Recovery would overwrite an immutable asset/run')
    # Validate completely before copying. The normal validator checks photo hashes after restoration.
    for path in files:
        relative = path.relative_to(source)
        if relative.parts[0] in {'assets', 'runs'}:
            immutable_bytes(directory / relative, path.read_bytes())
    if (source / 'latest.json').exists():
        atomic(directory / 'latest.json', read(source / 'latest.json'))
    atomic(directory / 'state.json', incoming)
    atomic(request_path, {**request, 'completed': True, 'recoveredAt': now()})
    print('Recovered collection artifact run', request['runId'])


if __name__ == '__main__':
    recover(Path(__file__).resolve().parents[1], Path(sys.argv[1]))
