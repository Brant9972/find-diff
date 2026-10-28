"""Hash-bound exchange with the external ChatGPT reviewer; never auto-approve."""
import hashlib
from .core import atomic, contained, read
from .sources import now


PENDING_STATUSES = {'pending_review', 'pending_evidence', 'legacy_requires_review', 'candidate_ready'}


def _decision_key(decision):
    """Delivery metadata is not a new review decision or an instruction to restart work."""
    return (decision.get('personId'), decision.get('candidateId'), decision.get('gameSha256'),
            decision.get('decision'), decision.get('reason', '').strip())


def _previous_review(row, candidate):
    # Upgrade states created before candidate-scoped review records existed.
    histories = candidate.get('externalReviewHistory', [])
    return (candidate.get('chatgptReview') or row.get('chatgptReviews', {}).get(candidate['id'])
            or (histories[-1] if histories else None)
            or (row.get('chatgptReview') if row.get('chatgptReview', {}).get('candidateId') == candidate['id'] else None))


def consume(root, directory, state):
    path = directory / 'chatgpt-review/latest.json'
    document = read(path)
    if document is None:
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if document.get('schemaVersion') != 1 or document.get('releaseGate') != 'DRAFT_ONLY_NOT_PLAYABLE':
        raise ValueError('Unsupported ChatGPT handoff schema/release gate')
    entries = []
    for field in ('decisions', 'newCandidates'):
        records = document.get(field, [])
        if not isinstance(records, list):
            raise ValueError('ChatGPT ' + field + ' must be an array')
        entries.extend((field, decision) for decision in records)
    changes, seen, person_ids = [], set(), []
    primary = {}
    for field, decision in entries:
        if not isinstance(decision, dict):
            raise ValueError('ChatGPT decision must be an object')
        try:
            pid, cid = decision['personId'], decision['candidateId']
            row = state['people'][pid]
            candidate = next(c for c in row['candidates'] if c['id'] == cid)
        except (KeyError, StopIteration, TypeError) as exc:
            raise ValueError('Unknown ChatGPT person/candidate') from exc
        if (pid, cid) in seen:
            raise ValueError('Duplicate ChatGPT decision')
        seen.add((pid, cid))
        if pid not in person_ids:
            person_ids.append(pid)
        primary.setdefault(pid, decision)  # decisions precede newCandidates, keeping old callers compatible.
        if decision.get('decision') not in {'reject', 'pending'} or not isinstance(decision.get('reason'), str) or not decision['reason'].strip():
            raise ValueError('This preliminary exchange accepts reject/pending only; no automated approval')
        image = contained(root, candidate['gamePath'])
        if (not decision.get('gameSha256') or decision['gameSha256'] != candidate.get('gameSha256')
                or not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != decision['gameSha256']):
            raise ValueError('Stale ChatGPT photo hash for ' + pid + '/' + cid)
        previous = _previous_review(row, candidate)
        changed = previous is None or _decision_key(previous) != _decision_key(decision)
        protected = row['status'] in {'approved', 'published'} or candidate.get('status') in {'approved', 'published'}
        if protected and changed:
            raise ValueError('ChatGPT preliminary review cannot overwrite approved/published people')
        changes.append((row, candidate, decision, field, changed, protected))
    # Validate current bytes even when a previously seen JSON is presented again.
    if state.get('chatgptReview', {}).get('sha256') == digest:
        return state['chatgptReview']
    # Validate the complete handoff before any archive, state mutation, or candidate status change.
    archive = directory / 'chatgpt-review/received' / (digest + '.json')
    if not archive.exists():
        atomic(archive, document)
    touched = set()
    for row, candidate, decision, field, changed, protected in changes:
        if protected:
            continue
        pid, cid = row['personId'], candidate['id']
        entry = {**decision, 'sourceReviewSha256': digest, 'reviewType': document.get('reviewType'),
                 'sourceCommit': document.get('sourceCommit'), 'handoffCollection': field}
        row.setdefault('chatgptReviews', {})[cid] = entry
        candidate['chatgptReview'] = entry
        if primary[pid]['candidateId'] == cid:
            row['chatgptReview'] = entry
        if not changed:
            continue
        touched.add(pid)
        candidate.setdefault('externalReviewHistory', []).append(entry)
        candidate['eligibleForLive'] = False
        if decision['decision'] == 'reject':
            candidate['status'] = 'rejected'
        else:
            candidate['status'] = 'pending_evidence'
            candidate['evidenceRequest'] = decision['reason']
    # Recompute once per changed person so rejecting an old photo cannot erase another
    # candidate's pending review, and an unchanged decision cannot reset a failed retry.
    for pid in touched:
        row = state['people'][pid]
        row['nextRetryAt'] = None
        if any(c.get('gamePath') and c.get('status') in PENDING_STATUSES for c in row['candidates']):
            row['status'] = 'pending_review'
        else:
            row['status'] = 'rejected'
    state['chatgptReview'] = {
        'sha256': digest, 'sourceCommit': document.get('sourceCommit'), 'sourceRun': document.get('sourceRun'),
        'receivedAt': now(), 'personIds': person_ids,
        'candidateRefs': [{'personId': d['personId'], 'candidateId': d['candidateId'], 'gameSha256': d['gameSha256'],
                           'decision': d['decision'], 'collection': field} for _, _, d, field, _, _ in changes],
        'counts': {'reject': sum(d['decision'] == 'reject' for _, _, d, _, _, _ in changes),
                   'pending': sum(d['decision'] == 'pending' for _, _, d, _, _, _ in changes)},
        'peopleCounts': {'reviewed': len(person_ids),
                         'pending': len({d['personId'] for _, _, d, _, _, _ in changes if d['decision'] == 'pending'}),
                         'reject': len({d['personId'] for _, _, d, _, _, _ in changes if d['decision'] == 'reject'})},
        'changedCandidates': sum(changed for _, _, _, _, changed, _ in changes),
    }
    atomic(directory / 'state.json', state)
    return state['chatgptReview']
