"""Durable review-only processing. No code here writes a playable bank."""
import contextlib
import datetime
import hashlib
import io
import json
import os
import re
import sys
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import unquote

from .sources import SourceError, identity, now, rights, source_key

STATUSES = {'not_started', 'searching', 'download_failed', 'no_suitable_source', 'candidate_ready', 'pending_review', 'rejected', 'approved', 'published'}
BLOCKED = ('funeral', 'mourning', 'memorial', 'obituary', 'waxwork', 'statue', 'sculpture', 'tussauds', '葬禮', '丧礼', '喪禮', '追思', '告別式', '告别式', '蠟像', '蜡像', '雕像', 'ai-generated', 'ai generated')


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def immutable_bytes(path, data):
    """Publish a complete asset atomically without replacing an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError('Immutable asset differs from existing bytes')
    finally:
        temp.unlink(missing_ok=True)


@contextlib.contextmanager
def lock(directory):
    """Kernel advisory lock is released automatically after crashes; never delete the lock inode."""
    import fcntl
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another media pipeline process owns this output directory') from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def contained(root, relative):
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Asset path escapes singer directory')
    return target


def protected(root):
    """Include all committed-style singer data, excluding expansion staging outputs."""
    paths = [p for p in root.rglob('*') if p.is_file() and 'expansion-1500' not in p.relative_to(root).parts and '__pycache__' not in p.parts]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def git_json(root, ref, filename):
    return json.loads(subprocess.check_output(['git', '-C', str(root), 'show', ref + ':singer/' + filename]))


def live_people(root, ref=None):
    result = {}
    for filename in ('questions.json', 'actors.json', 'variety.json'):
        for row in (git_json(root, ref, filename) if ref else read(root / filename, {'questions': []}))['questions']:
            result[row['id']] = row
    return result


def rejection_keys(root, ref=None):
    keys = {source_key(x.get('source')) for x in read(root / 'photo-review.json', {}).get('rejected', []) if x.get('source')}
    if ref:
        keys.update(source_key(x.get('source')) for x in git_json(root, ref, 'photo-review.json').get('rejected', []) if x.get('source'))
    legacy = read(root / 'expansion-1500/draft-media-index.json', {}).get('items', [])
    keys.update(source_key(x.get('source')) for x in legacy if x.get('source') and (x.get('reviewStatus', '').startswith('rejected') or x.get('reviewStatus') == 'needs_alternative_source'))
    return keys


def apply_rejections(state, rejected):
    """Apply newly received legacy rejections, preserving explicit approvals and live people."""
    for row in state['people'].values():
        if row['status'] in {'approved', 'published'}:
            continue
        for candidate in row['candidates']:
            if candidate.get('status') != 'approved' and source_key(candidate.get('source')) in rejected:
                candidate['status'] = 'rejected'
                warning = 'Source rejected by existing review records'
                if warning not in candidate.setdefault('warnings', []):
                    candidate['warnings'].append(warning)
        if row['status'] in {'pending_review', 'candidate_ready'} and not any(c.get('status') in {'pending_review', 'legacy_requires_review'} for c in row['candidates']):
            row['status'], row['nextRetryAt'] = 'rejected', None


def initialise(root, state_dir, active=None):
    state = read(state_dir / 'state.json')
    if state:
        if state.get('schemaVersion') != 2:
            raise ValueError('Unsupported pipeline state schema')
        return state
    plan = read(root / 'expansion-1500/release-plan-20261028.json')
    legacy = {x['candidateId']: x for x in read(root / 'expansion-1500/draft-media-index.json', {}).get('items', [])}
    active = live_people(root) if active is None else active
    people = {}
    for person in plan['selectedNew']:
        pid = person['plannedQuestionId']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', pid):
            raise ValueError('Invalid plannedQuestionId')
        if pid in people:
            raise ValueError('Duplicate plannedQuestionId: ' + pid)
        old = legacy.get(person['candidateId'], {})
        row = {'personId': pid, 'candidateId': person['candidateId'], 'name': person['name'], 'status': 'not_started',
               'attempts': 0, 'nextRetryAt': None, 'candidates': [], 'history': [], 'legacyRecord': old}
        if pid in active:
            row['status'] = 'published'
        elif old.get('reviewStatus') == 'approved':
            row['status'] = 'approved'
        elif old.get('reviewStatus', '').startswith('rejected') or old.get('reviewStatus') == 'needs_alternative_source':
            row['status'] = 'rejected'
        elif old.get('error'):
            row['status'] = 'no_suitable_source'
            row['lastFailure'] = {'code': 'legacy_failure', 'message': old['error'], 'retryable': True}
        if old.get('draftPhoto'):
            asset = contained(root, old['draftPhoto'])
            exists = asset.exists()
            digest = hashlib.sha256(asset.read_bytes()).hexdigest() if exists else None
            intact = exists and digest == old.get('sha256')
            candidate = {'id': 'legacy-' + pid, 'personId': pid, 'source': old.get('source', ''),
                         'article': old.get('article', ''), 'artist': old.get('artist', ''), 'license': old.get('license', ''),
                         'licenseUrl': old.get('licenseUrl', ''), 'gamePath': old['draftPhoto'], 'gameSha256': old.get('sha256'),
                         'reveal': old.get('revealDraft', {}), 'status': 'legacy_requires_review', 'rightsStatus': 'needs_review',
                         'warnings': ['Legacy provenance is incomplete; original URL/licence URL may be missing', old.get('qualityWarning', '')],
                         'validation': {'legacyAssetIntact': intact}, 'humanReview': None, 'eligibleForLive': False}
            if row['status'] == 'rejected':
                candidate['status'] = 'rejected'
            elif row['status'] not in {'published', 'approved'} and intact:
                row['status'] = 'pending_review'
            row['candidates'].append(candidate)
        people[pid] = row
    return {'schemaVersion': 2, 'createdAt': now(), 'releaseGate': 'DRAFT_ONLY_NOT_PLAYABLE', 'people': people}


def valid_reveal(reveal):
    try:
        ends = []
        for key in ('eyes', 'nose', 'mouth', 'chin'):
            x0, y0, x1, y1 = reveal[key]
            if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
                return False
            ends.append(y1)
        return ends == sorted(set(ends)) and reveal['full'] == [0, 0, 1, 1]
    except (KeyError, ValueError, TypeError):
        return False


class Cropper:
    def __init__(self, root):
        self.root, self.tools = root, None

    def __call__(self, blob):
        from PIL import Image, ImageOps
        # Decode and bound dimensions BEFORE invoking the existing landmark pipeline.
        with Image.open(io.BytesIO(blob)) as im:
            if im.width * im.height > 30_000_000:
                raise ValueError('Source exceeds 30 megapixels')
            im.verify()
        with Image.open(io.BytesIO(blob)) as im:
            original_size = ImageOps.exif_transpose(im).size
        if min(original_size) < 180:
            raise ValueError('Source resolution below 180 pixels')
        if self.tools is None:
            sys.path.insert(0, str(self.root))
            try:
                import portrait_tools
            except Exception as exc:
                raise SourceError('processor_unavailable', 'YuNet initialisation failed: ' + str(exc)[:200]) from exc
            self.tools = portrait_tools
        image, reveal = self.tools.crop_face(blob)
        import cv2
        import numpy as np
        sharpness = float(cv2.Laplacian(np.asarray(image.convert('L')), cv2.CV_64F).var())
        gray = np.asarray(image.convert('L'))
        exposure = float(np.mean(gray > 248))
        if sharpness < 65:
            raise ValueError('Blurred crop: sharpness below 65')
        if exposure > .55:
            raise ValueError('Overexposed crop: more than 55% near-white pixels')
        if image.size != (600, 720) or not valid_reveal(reveal):
            raise ValueError('Invalid crop dimensions or reveal boundaries')
        buf = io.BytesIO()
        image.save(buf, 'JPEG', quality=92, optimize=True)
        return buf.getvalue(), reveal, {'decoded': True, 'size': [600, 720], 'originalSize': list(original_size), 'sharpness': round(sharpness, 2), 'overexposedFraction': exposure}


def ready(row):
    return [c for c in row['candidates'] if c.get('status') == 'pending_review']


def process(person, row, root, directory, providers, http, crop, rejected, max_candidates=3, max_attempts=24, deadline=None, checkpoint=None, active=None):
    row['status'] = 'searching'
    row['attempts'] += 1
    row['lastAttemptAt'] = now()
    if checkpoint:
        checkpoint()
    errors, seen, tried = [], {source_key(c.get('source')) for c in row['candidates'] if c.get('status') != 'metadata_only'}, 0
    rejected = rejected | {source_key(c.get('source')) for c in row['candidates'] if c.get('status') == 'rejected'}
    used = {source_key(q.get('attribution', {}).get('source')) for q in (live_people(root) if active is None else active).values()}
    other_images = [c for pid, p in read(directory / 'state.json', {'people': {}})['people'].items() if pid != row['personId'] for c in p['candidates']]
    for provider in providers:
        provider_tried = 0
        if len(ready(row)) >= max_candidates or (deadline and time.monotonic() >= deadline):
            break
        query = {'time': now(), 'provider': provider.name, 'attempt': row['attempts']}
        row['history'].append(query)
        try:
            for item in provider.search(person, http, row['attempts'] - 1):
                if len(ready(row)) >= max_candidates or provider_tried >= max(1, max_attempts // max(1, len(providers))) or (deadline and time.monotonic() >= deadline):
                    break
                key = source_key(item.get('source'))
                if not item.get('source') or not item.get('url'):
                    errors.append({'provider': provider.name, 'code': 'invalid_metadata', 'message': 'Missing image URL or source page'})
                    continue
                if key in seen or key in rejected or key in used:
                    continue
                seen.add(key)
                tried += 1
                provider_tried += 1
                text = unquote(' '.join(str(item.get(k, '')) for k in ('source', 'url', 'caption', 'filename'))).casefold()
                if any(word in text for word in BLOCKED):
                    errors.append({'provider': provider.name, 'source': item['source'], 'code': 'excluded_context', 'message': 'Disallowed memorial/statue/generated context'})
                    continue
                cid = hashlib.sha256((row['personId'] + '\n' + item['source'] + '\n' + item['url']).encode()).hexdigest()[:20]
                candidate = {**item, 'id': cid, 'personId': row['personId'], 'rightsStatus': rights(item), 'eligibleForLive': False,
                             'humanReview': None, 'status': 'metadata_only', 'warnings': ['Identity, iconic appearance, eyes/occlusion and watermark require human review']}
                evidence = candidate.get('identityEvidence', {})
                matches = identity(person, item.get('caption', '') + ' ' + item.get('filename', '') + ' ' + evidence.get('caption', ''))
                candidate['identityEvidence'] = {**evidence, 'captionAliasMatches': matches, 'visualIdentityVerified': False}
                identity_supported = bool(matches or evidence.get('matchedAliases') or (evidence.get('wikidataId') and evidence.get('claim') == 'P18'))
                # Refresh metadata for the same immutable URL pair, without touching reviewed/downloaded candidates.
                row['candidates'] = [c for c in row['candidates'] if not (c['id'] == cid and c.get('status') == 'metadata_only')]
                if not identity_supported:
                    candidate['warnings'].append('No name-bearing caption/article/entity evidence: image not downloaded')
                    row['candidates'].append(candidate)
                    errors.append({'provider': provider.name, 'source': item['source'], 'code': 'identity_unconfirmed', 'message': 'Search result alone does not establish depicted identity'})
                    if checkpoint:
                        checkpoint()
                    continue
                if candidate['rightsStatus'] != 'open_license_metadata':
                    candidate['warnings'].append('Licence insufficient: image not downloaded')
                    row['candidates'].append(candidate)
                    errors.append({'provider': provider.name, 'source': item['source'], 'code': 'license_unclear', 'message': 'Source metadata retained; no download without reusable licence metadata'})
                    if checkpoint:
                        checkpoint()
                    continue
                try:
                    blob = http.get(item['url'])
                    digest = hashlib.sha256(blob).hexdigest()
                    image, reveal, validation = crop(blob)
                    game_digest = hashlib.sha256(image).hexdigest()
                    if any(c.get('originalSha256') == digest or c.get('gameSha256') == game_digest for c in other_images):
                        errors.append({'provider': provider.name, 'source': item['source'], 'code': 'image_used_for_other_person', 'message': 'Image hash already belongs to another person; identity conflict'})
                        continue
                    duplicate = next((c for c in row['candidates'] if c.get('originalSha256') == digest or c.get('gameSha256') == game_digest), None)
                    if duplicate:
                        duplicate.setdefault('alternateSources', []).append(item)
                        errors.append({'provider': provider.name, 'source': item['source'], 'code': 'duplicate_image', 'message': 'Same image already saved under another source'})
                        if checkpoint:
                            checkpoint()
                        continue
                    base = directory / 'assets' / row['personId'] / cid / digest[:12]
                    base.mkdir(parents=True, exist_ok=True)
                    raw_path, game_path = base / 'original.bin', base / (game_digest[:12] + '.jpg')
                    for path, data in ((raw_path, blob), (game_path, image)):
                        immutable_bytes(path, data)
                    candidate.update({'status': 'pending_review', 'originalPath': str(raw_path.relative_to(root)), 'gamePath': str(game_path.relative_to(root)),
                                      'originalSha256': digest, 'gameSha256': hashlib.sha256(image).hexdigest(), 'reveal': reveal, 'validation': validation})
                    row['candidates'].append(candidate)
                except (SourceError, ValueError, OSError, ImportError) as exc:
                    code = getattr(exc, 'code', 'image_validation_failed' if not isinstance(exc, ImportError) else 'processor_unavailable')
                    errors.append({'provider': provider.name, 'source': item['source'], 'url': item['url'], 'code': code, 'message': str(exc)[:400]})
                # Checkpoint candidates immediately; a later failed source must not lose them.
                if checkpoint:
                    checkpoint()
        except Exception as exc:
            errors.append({'provider': provider.name, 'code': getattr(exc, 'code', 'source_error'), 'message': str(exc)[:400]})
        query['finishedAt'] = now()
    row['lastErrors'] = errors
    row['history'].append({'time': now(), 'errors': errors, 'candidatesTried': tried})
    if ready(row):
        row['status'], row['nextRetryAt'] = 'pending_review', None
    else:
        network_codes = {'network_error', 'proxy_access_denied', 'download_failed', 'http_429', 'http_403', 'http_500', 'http_502', 'http_503', 'http_504', 'processor_unavailable'}
        row['status'] = 'download_failed' if any(e['code'] in network_codes for e in errors) else 'no_suitable_source'
        row['nextRetryAt'] = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=min(24 * 7, 2 ** min(row['attempts'], 7)))).isoformat()
        row['lastFailure'] = {'code': row['status'], 'retryable': True, 'message': 'See lastErrors' if errors else 'No usable candidates returned by sources'}
    row['updatedAt'] = now()
