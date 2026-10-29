"""Stage reproducible 600x720 *drafts* from an immutable source-only review commit.

No face identity or licensing decision is inferred from cropping. Nothing here
modifies singer/photos, main, the official questions, or review approvals.
"""
import copy
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from media_pipeline.core import immutable_bytes, valid_reveal
from media_pipeline.evidence import previews


def _git_file(commit, path):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Manual recrop requires a full immutable source commit SHA')
    if not path.startswith('singer/expansion-1500/pipeline/') or '..' in Path(path).parts:
        raise ValueError('Refusing source path outside draft pipeline')
    return subprocess.check_output(['git', 'show', commit + ':' + path])


def stage_manual_recrops(root, directory, state, request, run_id, live):
    if request.get('schemaVersion') != 1 or request.get('releaseGate') != 'MANUAL_CROP_STAGING_ONLY_NO_LIVE':
        raise ValueError('Not a source-only manual recrop request')
    commit = request['sourceCommit']
    source_state = json.loads(_git_file(commit, 'singer/expansion-1500/pipeline/state.json'))
    scanned = []
    for item in request.get('items', []):
        pid = item['personId']
        if pid in live:
            continue
        row = state['people'].get(pid)
        source_row = source_state['people'].get(pid)
        if not row or not source_row or row['name'] != source_row['name']:
            raise ValueError('Person identity/roster mismatch: ' + pid)
        if row['status'] in {'published', 'approved', 'duplicate_existing'}:
            continue
        source = next((c for c in source_row['candidates']
                       if c['id'] == item['sourceCandidateId']), None)
        if not source or source.get('status') != 'manual_crop_required':
            raise ValueError('Not a saved source-only candidate: ' + pid)
        if source.get('rightsStatus') != 'open_license_metadata':
            raise ValueError('Source is not licensed for cropping: ' + pid)
        if source.get('originalSha256') != item['sourceSha256']:
            raise ValueError('Source SHA differs from human-reviewed request: ' + pid)
        raw = _git_file(commit, 'singer/' + source['originalPath'])
        if hashlib.sha256(raw).hexdigest() != item['sourceSha256']:
            raise ValueError('Source image bytes differ: ' + pid)
        if not any(c['id'] == source['id'] for c in row['candidates']):
            source_path = directory / 'assets' / pid / source['id'] / item['sourceSha256'][:12] / 'original.bin'
            immutable_bytes(source_path, raw)
            source_copy = copy.deepcopy(source)
            source_copy['originalPath'] = str(source_path.relative_to(root))
            source_copy['eligibleForLive'] = False
            source_copy['humanReview'] = None
            row['candidates'].append(source_copy)
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
        x0, y0, x1, y1 = item['box']
        if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
            raise ValueError('Manual crop outside original image: ' + pid)
        if abs((x1-x0)/(y1-y0) - 5/6) > 0.001:
            raise ValueError('Manual crop must be exactly 5:6: ' + pid)
        reveal = item['reveal']
        if not valid_reveal(reveal):
            raise ValueError('Invalid manual five-stage reveal: ' + pid)
        cropped = image.crop((x0, y0, x1, y1)).resize((600, 720), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        cropped.save(output, format='JPEG', quality=94, subsampling=0)
        game = output.getvalue()
        game_sha = hashlib.sha256(game).hexdigest()
        cid = 'manualrecrop-' + game_sha[:20]
        if any(c['id'] == cid for c in row['candidates']):
            continue
        base = directory / 'assets' / pid / cid / item['sourceSha256'][:12]
        raw_path, game_path = base / 'original.bin', base / (game_sha[:12] + '.jpg')
        immutable_bytes(raw_path, raw)
        immutable_bytes(game_path, game)
        candidate = copy.deepcopy(source)
        old_failure = candidate.pop('cropFailure', '')
        candidate.update({
            'id': cid,
            'parentCandidateId': source['id'],
            'parentSourceSha256': item['sourceSha256'],
            'status': 'pending_review',
            'originalPath': str(raw_path.relative_to(root)),
            'originalSha256': item['sourceSha256'],
            'gamePath': str(game_path.relative_to(root)),
            'gameSha256': game_sha,
            'reveal': reveal,
            'validation': {'decoded': True, 'size': [600, 720],
                           'manualGeometryRequiresHumanVisualQA': True},
            'manualCropEvidence': {'sourceCommit': commit, 'sourceCandidateId': source['id'],
                                   'sourceSha256': item['sourceSha256'],
                                   'sourceSize': [image.width, image.height],
                                   'cropBox': item['box'], 'parentCropFailure': old_failure,
                                   'reviewerNotes': item.get('notes', '')},
            'humanReview': None,
            'eligibleForLive': False,
            'warnings': ['Manually staged source-pixel crop; original person identity, author, rights, image quality and every reveal stage require independent human approval.'],
        })
        row['candidates'].append(candidate)
        row['status'] = 'pending_review'
        row['lastRunId'] = run_id
        row['lastRunNewCandidateIds'] = [cid]
        row['nextRetryAt'] = None
        row['lastErrors'] = []
        row.setdefault('history', []).append({
            'provider': 'manual_recrop', 'runId': run_id, 'sourceCommit': commit,
            'candidateId': cid, 'sourceCandidateId': source['id']})
        previews(root, directory, candidate)
        scanned.append(pid)
    return scanned
