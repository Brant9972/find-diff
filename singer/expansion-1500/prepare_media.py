#!/usr/bin/env python3
"""Search and prepare review candidates only. Never modify live banks or publish."""
import argparse
import datetime
import json
import re
import sys
import time
import uuid
from pathlib import Path

from media_pipeline.core import Cropper, apply_rejections, atomic, contained, initialise, live_people, lock, process, protected, read, rejection_keys
from media_pipeline.review import import_decisions, report
from media_pipeline.handoff import consume
from media_pipeline.evidence import supplement
from media_pipeline.sources import HTTP, CommonsSearch, Official, Openverse, Wikimedia


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--max-minutes', type=float, default=30)
    parser.add_argument('--max-candidates', type=int, choices=range(1, 4), default=3)
    parser.add_argument('--providers', default='commons,openverse,wikimedia,official')
    parser.add_argument('--person-id', action='append', default=[])
    parser.add_argument('--retry-failed', action='store_true', help='Only failed/rejected/interrupted records; bypass retry cooldown')
    parser.add_argument('--render-only', action='store_true', help='Migrate/read state and generate review pages without network calls')
    parser.add_argument('--import-review', type=Path, help='Explicit decisions exported by the external human review workflow; never use for auto-approval')
    parser.add_argument('--official-sources', type=Path)
    parser.add_argument('--review-round', action='store_true', help='Process only fixed-location ChatGPT handoff targets, including pending evidence')
    parser.add_argument('--person-seconds', type=float, default=60, help='Per-person network/search budget')
    parser.add_argument('--live-ref', help='Read published banks/blacklist from a fetched Git ref, without changing the checkout')
    args = parser.parse_args(argv)
    if not 0 <= args.limit <= 300 or not 0 < args.max_minutes <= 120 or not 1 <= args.person_seconds <= 300:
        parser.error('limit must be 0..300; max-minutes must be >0 and <=120')
    root = Path(__file__).resolve().parents[1]
    directory = root / 'expansion-1500/pipeline'
    before = protected(root)
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    names = args.providers.split(',')
    if not names or any(not n for n in names):
        parser.error('At least one provider is required')
    if set(names) - {'commons', 'wikimedia', 'openverse', 'official'}:
        parser.error('Unknown provider')
    with lock(directory):
        active = live_people(root, args.live_ref)
        state = initialise(root, directory, active=active)
        plan = read(root / 'expansion-1500/release-plan-20261028.json')
        people = {p['plannedQuestionId']: p for p in plan['selectedNew']}
        if set(args.person_id) - people.keys():
            parser.error('Unknown person ID')
        # Current banks override stale state. Names/articles prevent retired alias IDs being searched again.
        from media_pipeline.sources import norm
        active_names = {norm(q['name']) for q in active.values()}
        for pid, row in state['people'].items():
            if pid in active:
                row['status'] = 'published'
            elif norm(row['name']) in active_names:
                row['status'] = 'published'
                row['skipReason'] = 'Existing canonical name; no new person count'
        handoff = consume(root, directory, state)
        if args.review_round and not handoff:
            parser.error('No ChatGPT review handoff found at pipeline/chatgpt-review/latest.json')
        rejected = rejection_keys(root, args.live_ref)
        from media_pipeline.sources import source_key
        rejected.update(source_key(c.get('source')) for r in state['people'].values() for c in r['candidates'] if c.get('status')=='rejected' and c.get('source'))
        apply_rejections(state, rejected)
        atomic(directory / 'state.json', state)
        if args.import_review:
            import_decisions(root, directory, state, read(args.import_review))
        scanned = []
        try:
            if not args.render_only and not args.import_review:
                records = read(args.official_sources, []) if args.official_sources else []
                providers = {'commons': CommonsSearch(), 'wikimedia': Wikimedia(), 'openverse': Openverse(), 'official': Official(records)}
                deadline = time.monotonic() + args.max_minutes * 60
                http, crop = HTTP(attempts=2, timeout=12, budget=deadline), Cropper(root)
                # Rotate providers across attempts so a failing first provider cannot starve alternatives.
                queue = sorted(state['people'].values(), key=lambda p: (p['personId'] not in (handoff or {}).get('personIds', []), people[p['personId']].get('priority') != 'A', p.get('attempts', 0), p['personId']))
                for row in queue:
                    if len(scanned) >= args.limit or time.monotonic() >= deadline:
                        break
                    if args.review_round and row['personId'] not in handoff['personIds']:
                        continue
                    if args.person_id and row['personId'] not in args.person_id:
                        continue
                    needs_evidence = row.get('chatgptReview', {}).get('decision') == 'pending'
                    if row['status'] in {'approved', 'published'} or (row['status'] in {'pending_review', 'candidate_ready'} and not needs_evidence):
                        continue
                    failed = row['status'] in {'download_failed', 'no_suitable_source', 'rejected', 'searching'}
                    if args.retry_failed and not failed and not needs_evidence:
                        continue
                    retry = row.get('nextRetryAt')
                    if retry and not args.retry_failed and not args.review_round and datetime.datetime.fromisoformat(retry) > datetime.datetime.now(datetime.timezone.utc):
                        continue
                    scanned.append(row['personId'])
                    prior_candidates = {c['id'] for c in row['candidates'] if c.get('gamePath')}
                    row['lastRunId'] = run_id
                    row['lastRunNewCandidateIds'] = []
                    atomic(directory / 'state.json', state)
                    person_deadline = min(deadline, time.monotonic() + args.person_seconds)
                    http.budget = person_deadline
                    selected = [providers[n] for n in names]
                    shift = row['attempts'] % len(selected)
                    selected = selected[shift:] + selected[:shift]
                    try:
                        person = dict(people[row['personId']])
                        review = row.get('chatgptReview', {})
                        person['reviewReason'] = review.get('reason', '')
                        person['excludedCaptionNames'] = re.findall(r'涉及([^；，。 ]+)', person['reviewReason'])
                        person['reviewSearchQuery'] = person['name'] + ' ' + ' '.join(person.get('representativeWorks', [])) + ' portrait'
                        if needs_evidence:
                            row['attempts'] += 1
                            supplement(root, directory, row, person, http)
                            row['nextRetryAt'] = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)).isoformat()
                        else:
                            process(person, row, root, directory, selected, http, crop, rejected, args.max_candidates, deadline=person_deadline, checkpoint=lambda: atomic(directory / 'state.json', state), active=active)
                    except Exception as exc:
                        row['status'] = 'download_failed'
                        row['lastErrors'] = [{'code': 'processing_error', 'message': str(exc)[:400]}]
                    row['lastRunNewCandidateIds'] = [c['id'] for c in row['candidates'] if c.get('status')=='pending_review' and c.get('gamePath') and c['id'] not in prior_candidates]
                    atomic(directory / 'state.json', state)
                    print(row['personId'], row['name'], row['status'], flush=True)
        finally:
            if protected(root) != before:
                raise RuntimeError('Production protection check failed; do not commit this run')
            summary = report(root, directory, state, run_id, scanned)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print('Review:', directory / 'runs' / run_id / 'review.html')
            if handoff:
                atomic(directory / 'codex-response/latest.json', {'schemaVersion': 1, 'sourceReviewSha256': handoff['sha256'], 'sourceReviewCommit': handoff.get('sourceCommit'), 'releaseGate': 'DRAFT_ONLY_NOT_PLAYABLE', 'runId': run_id, 'reviewIndex': str((directory/'runs'/run_id/'review-index.json').relative_to(root)), 'summary': summary, 'items': [{'personId': pid, 'request': state['people'][pid].get('chatgptReview'), 'status': state['people'][pid]['status'], 'errors': state['people'][pid].get('lastErrors', []), 'candidateIds': [c['id'] for c in state['people'][pid]['candidates'] if c.get('status') in {'pending_review','pending_evidence'}]} for pid in handoff['personIds']]})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
