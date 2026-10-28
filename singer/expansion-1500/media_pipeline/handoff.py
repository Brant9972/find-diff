"""Hash-bound exchange with the external ChatGPT reviewer; never auto-approve."""
import hashlib
from .core import atomic, contained, read
from .sources import now


def consume(root, directory, state):
    path = directory / 'chatgpt-review/latest.json'
    document = read(path)
    if document is None:
        return None
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if document.get('schemaVersion') != 1 or document.get('releaseGate') != 'DRAFT_ONLY_NOT_PLAYABLE':
        raise ValueError('Unsupported ChatGPT handoff schema/release gate')
    if state.get('chatgptReview', {}).get('sha256') == digest:
        return state['chatgptReview']
    changes, seen = [], set()
    for decision in document.get('decisions', []):
        pid, cid = decision['personId'], decision['candidateId']
        if (pid, cid) in seen:
            raise ValueError('Duplicate ChatGPT decision')
        seen.add((pid, cid))
        row = state['people'][pid]
        candidate = next(c for c in row['candidates'] if c['id'] == cid)
        if row['status'] in {'approved', 'published'}:
            raise ValueError('ChatGPT preliminary review cannot overwrite approved/published people')
        if decision['decision'] not in {'reject', 'pending'} or not decision.get('reason', '').strip():
            raise ValueError('This preliminary exchange accepts reject/pending only; no automated approval')
        image = contained(root, candidate['gamePath'])
        if decision['gameSha256'] != candidate['gameSha256'] or hashlib.sha256(image.read_bytes()).hexdigest() != decision['gameSha256']:
            raise ValueError('Stale ChatGPT photo hash for ' + pid)
        changes.append((row, candidate, decision))
    # Validate the complete handoff before mutating a single candidate.
    archive = directory / 'chatgpt-review/received' / (digest + '.json')
    if not archive.exists():
        atomic(archive, document)
    for row, candidate, decision in changes:
        entry = {**decision, 'sourceReviewSha256': digest, 'reviewType': document.get('reviewType'), 'sourceCommit': document.get('sourceCommit')}
        row['chatgptReview'] = entry
        row['nextRetryAt'] = None
        candidate.setdefault('externalReviewHistory', []).append(entry)
        candidate['eligibleForLive'] = False
        if decision['decision'] == 'reject':
            candidate['status'], row['status'] = 'rejected', 'rejected'
        else:
            candidate['status'], row['status'] = 'pending_evidence', 'pending_review'
            candidate['evidenceRequest'] = decision['reason']
    state['chatgptReview'] = {'sha256': digest, 'sourceCommit': document.get('sourceCommit'), 'sourceRun': document.get('sourceRun'), 'receivedAt': now(), 'personIds': [r['personId'] for r, _, _ in changes], 'counts': {'reject': sum(d['decision']=='reject' for _,_,d in changes), 'pending': sum(d['decision']=='pending' for _,_,d in changes)}}
    atomic(directory / 'state.json', state)
    return state['chatgptReview']
