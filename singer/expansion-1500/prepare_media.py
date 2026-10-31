#!/usr/bin/env python3
"""One bounded bulk discovery batch, then one review package. Never publish a game."""
import argparse
import copy
import datetime
import re
import time
import uuid
from pathlib import Path
from media_pipeline.core import Cropper,apply_rejections,atomic,initialise,live_people,lock,protected,read,rejection_keys
from media_pipeline.handoff import consume
from media_pipeline.sources import CommonsSearch,CuratedCommons,EntityPortraits,Official,Openverse,Wikimedia,norm,source_key,HTTP
from media_pipeline.batch import SEARCH_REVISION,recover_checkpoints,run_batch
from media_pipeline.evidence import supplement
from media_pipeline.review import report
from media_pipeline.delivery import build_assets



def merge_caption_exclusions(person, review_reason):
    """Preserve human-curated false-identity exclusions when adding review hints.

    Previous batching silently replaced excludedCaptionNames with only names
    parsed from a transient review reason. This made rejected namesakes
    searchable again even though the release plan still excluded them.
    """
    curated = person.get('excludedCaptionNames', [])
    from_review = re.findall(r'涉及([^；，。 ]+)', review_reason or '')
    return list(dict.fromkeys(
        name.strip() for name in [*curated, *from_review]
        if isinstance(name, str) and name.strip()
    ))



def reconcile_live_people(state, people, active):
    """Fail closed on known live identities before any photo-source requests.

    A planned ID is published only if that *same ID* exists in the latest
    playable banks. Other matches are duplicates, not new published people.
    Match pinned Wikidata QIDs, canonical names, and unique strong
    canonical-to-alias links; never infer a duplicate from two generic
    nicknames or from a conflicting pair of pinned QIDs.
    """
    def qid(item):
        value = item.get('wikidataId') or item.get('wikidataQid')
        return value if isinstance(value, str) and re.fullmatch(r'Q[1-9][0-9]*', value) else None

    def strong_alias(value):
        key = norm(value)
        if re.fullmatch(r'[a-z0-9]+', key):
            return len(key) >= 5
        return len(key) >= 3

    canonical, aliases, qids = {}, {}, {}
    for live_id, question in active.items():
        name_key = norm(question.get('name', ''))
        if name_key:
            canonical.setdefault(name_key, set()).add(live_id)
        for alias in question.get('aliases', []):
            if isinstance(alias, str) and strong_alias(alias):
                aliases.setdefault(norm(alias), set()).add(live_id)
        if qid(question):
            qids.setdefault(qid(question), set()).add(live_id)

    def unique_identity(ids, candidate_qid):
        # Multiple questions in different banks can be the SAME person.
        # Different canonical people sharing a nickname are ambiguous.
        eligible = [live_id for live_id in ids
                    if not (candidate_qid and qid(active[live_id])
                            and qid(active[live_id]) != candidate_qid)]
        if len({norm(active[live_id].get('name', '')) for live_id in eligible}) != 1:
            return None
        return sorted(eligible)[0] if eligible else None

    for pid, row in state['people'].items():
        if pid in active:
            row['status'] = 'published'
            continue
        person = people.get(pid)
        if person is None:
            continue
        candidate_qid = qid(person)
        name_key = norm(person.get('name', row.get('name', '')))
        match, reason = None, None
        explicit = person.get('duplicateExistingCanonicalId')
        if explicit in active:
            match, reason = explicit, 'curated_duplicate_id'
        elif candidate_qid and qids.get(candidate_qid):
            match, reason = sorted(qids[candidate_qid])[0], 'wikidata_qid'
        elif name_key and canonical.get(name_key):
            match = unique_identity(canonical[name_key], candidate_qid)
            reason = 'canonical_name' if match else None
        if not match and name_key and strong_alias(name_key) and aliases.get(name_key):
            match = unique_identity(aliases[name_key], candidate_qid)
            reason = 'canonical_matches_live_alias' if match else None
        if not match:
            candidate_aliases = {
                norm(alias) for alias in [*person.get('aliases', []), *person.get('acceptedAnswers', [])]
                if isinstance(alias, str) and strong_alias(alias)
            }
            ids = set().union(*(canonical.get(key, set()) for key in candidate_aliases)) if candidate_aliases else set()
            match = unique_identity(ids, candidate_qid) if ids else None
            reason = 'candidate_alias_matches_live_canonical' if match else None
        if match:
            row['status'] = 'duplicate_existing'
            row['duplicateExistingCanonicalId'] = match
            row['duplicateMatchReason'] = reason
            row['duplicateMatchSource'] = 'live_preflight'
            row['nextRetryAt'] = None
        elif row.get('status') == 'published':
            # A stale state cannot prove publication when the latest live
            # questions no longer contain the planned ID or its identity.
            row['status'] = 'no_suitable_source'
            row['preflightWarning'] = 'previous_published_state_absent_from_current_live_banks'

def retained_source_targets(scanned, explicitly_requested):
    """Re-expose cached source pixels for explicit IDs even during cooldown."""
    return sorted(set(scanned) | set(explicitly_requested))


def load_preselected_backup_search_people(root):
    """Search only already-listed, separately preselected backup people.

    This adds a *draft search row*, never a released person or a change to the
    511 selectedNew release arithmetic. The source lead is not human approval.
    """
    directory = root / 'expansion-1500'
    spec = read(directory / 'pipeline/backup-photo-leads-20261030.json', {'people': []})
    if spec.get('releaseGate') != 'BACKUP_PHOTO_SEARCH_ONLY_NOT_PLAYABLE':
        raise ValueError('Backup search release gate must remain draft-only')
    original = {row['candidateId']: row for row in
                read(directory / 'taiwan-first-candidates-20261028.json')['candidates']
                if row.get('purpose') == 'backup'}
    preselected = {row['candidateId']: row for row in
                   read(directory / 'pipeline/backup-eligibility-review-20261029.json')['candidates']}
    result = {}
    for lead in spec['people']:
        candidate_id = lead['candidateId']
        base = original.get(candidate_id)
        reviewed = preselected.get(candidate_id)
        match = re.fullmatch(r'c1500-([0-9]{4})', candidate_id)
        if not match or not base or not reviewed or base['name'] != lead['name'] or reviewed['name'] != lead['name']:
            raise ValueError('Backup lead is not an existing preselected candidate')
        pid = 't1500_' + match.group(1)
        if lead.get('plannedQuestionId') != pid or lead.get('proposedPrimaryBank') != reviewed['proposedBank']:
            raise ValueError('Backup lead has inconsistent person ID or bank')
        filenames = lead.get('reviewExactCommonsFiles', [])
        if not 1 <= len(filenames) <= 3 or any(
                not (isinstance(f, str) and 1 <= len(f) <= 200
                     and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
                     and all(ch not in f for ch in ('/', chr(92), chr(10), chr(13))))
                for f in filenames):
            raise ValueError('Backup source filenames must be bounded image names')
        if pid in result:
            raise ValueError('Duplicate backup search person ID')
        person = copy.deepcopy(base)
        person.update(plannedQuestionId=pid, proposedPrimaryBank=reviewed['proposedBank'],
                      representativeWorks=lead.get('representativeWorks', []),
                      reviewExactCommonsFiles=filenames,
                      reviewVerifiedOriginalSources=lead.get('reviewVerifiedOriginalSources', []),
                      backupSearchOnly=True, photoStatus='not_prepared', qaStatus='not_releasable')
        result[pid] = person
    return result


def select_people(state,people,handoff,limit,review_only=False,retry_failed=False,person_ids=()):
    reviewed=set((handoff or {}).get('personIds',[]));queue=[]
    for pid,row in state['people'].items():
        if person_ids and pid not in person_ids:continue
        if review_only and pid not in reviewed:continue
        # Already staged reviewable pixels do not need another source search.
        if row['status'] in {'approved','published','pending_review','candidate_ready','duplicate_existing'}:continue
        if retry_failed and row['status'] not in {'download_failed','no_suitable_source','rejected','searching'}:continue
        retry=row.get('nextRetryAt')
        if retry and row.get('lastSearchRevision')==SEARCH_REVISION and not retry_failed:
            if datetime.datetime.fromisoformat(retry)>datetime.datetime.now(datetime.timezone.utc):continue
        queue.append(pid)
    queue.sort(key=lambda pid:(pid not in reviewed, state['people'][pid].get('attempts',0)>0,people[pid].get('priority')!='A',state['people'][pid].get('attempts',0),pid))
    return queue[:limit]



def requested_selection_audit(state, requested_ids, selected_ids, retry_failed=False,
                              revision=SEARCH_REVISION, current_time=None):
    """Explain why explicit targets did not enter a source-search queue.

    Diagnostic only: never overrides cooldowns, retries a rejected image,
    approves a photo, or changes the selected person IDs.
    """
    current_time = current_time or datetime.datetime.now(datetime.timezone.utc)
    selected = set(selected_ids)
    skipped = []
    for pid in requested_ids:
        if pid in selected:
            continue
        row = state['people'].get(pid)
        if row is None:
            reason, status = 'unknown_person', None
        else:
            status = row.get('status')
            if status in {'approved', 'published', 'pending_review',
                          'candidate_ready', 'duplicate_existing'}:
                reason = 'already_staged_or_published'
            elif retry_failed and status not in {
                    'download_failed', 'no_suitable_source', 'rejected', 'searching'}:
                reason = 'retry_failed_status_filter'
            elif (not retry_failed and row.get('lastSearchRevision') == revision
                  and row.get('nextRetryAt')):
                try:
                    retry_at = datetime.datetime.fromisoformat(row['nextRetryAt'])
                    if retry_at.tzinfo is None:
                        reason = 'invalid_retry_timestamp'
                    elif retry_at > current_time:
                        reason = 'cooldown'
                    else:
                        reason = 'other_selection_filter'
                except (TypeError, ValueError):
                    reason = 'invalid_retry_timestamp'
            else:
                reason = 'other_selection_filter'
        item = {'personId': pid, 'status': status, 'reason': reason}
        if row and row.get('nextRetryAt'):
            item['nextRetryAt'] = row['nextRetryAt']
        skipped.append(item)
    return skipped


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=40)
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--max-minutes',type=float,default=25)
    parser.add_argument('--person-seconds',type=float,default=60)
    parser.add_argument('--max-candidates',type=int,choices=range(1,4),default=3)
    parser.add_argument('--providers',default='entity,commons,openverse,official')
    parser.add_argument('--person-id',action='append',default=[])
    parser.add_argument('--retry-failed',action='store_true')
    parser.add_argument('--render-only',action='store_true')
    parser.add_argument('--manual-recrop-request',type=Path,help='Stage immutable source-only review photos with supplied crop geometry; never deploy')
    parser.add_argument('--import-review',type=Path)
    parser.add_argument('--official-sources',type=Path)
    parser.add_argument('--evidence-only',action='store_true',help='Explicitly refresh pending source evidence; not run on every batch')
    parser.add_argument('--review-round',action='store_true',help='Legacy restriction to reviewer target people only')
    parser.add_argument('--live-ref')
    args=parser.parse_args(argv)
    if not 0<=args.limit<=300 or not 1<=args.workers<=6 or not 0<args.max_minutes<=120 or not 1<=args.person_seconds<=300:parser.error('Invalid batch/time/worker limits')
    names=args.providers.split(',')
    if not names or set(names)-{'entity','commons','openverse','wikimedia','official','curated'}:parser.error('Unknown/empty provider')
    root=Path(__file__).resolve().parents[1];directory=root/'expansion-1500/pipeline';before=protected(root)
    run_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    with lock(directory):
        active=live_people(root,args.live_ref);state=initialise(root,directory,active=active)
        people={p['plannedQuestionId']:p for p in read(root/'expansion-1500/release-plan-20261028.json')['selectedNew']}
        backups=load_preselected_backup_search_people(root)
        if set(backups)&set(people):raise ValueError('Backup ID collides with selectedNew')
        people.update(backups)
        for pid,person in backups.items():
            if pid not in state['people']:
                state['people'][pid]={'personId':pid,'candidateId':person['candidateId'],
                                     'name':person['name'],'status':'not_started','attempts':0,
                                     'nextRetryAt':None,'candidates':[],'history':[],
                                     'backupSearchOnly':True}
            elif (state['people'][pid].get('candidateId') != person['candidateId']
                  or state['people'][pid].get('name') != person['name']):
                raise ValueError('Backup state identity mismatch')
        if set(args.person_id)-people.keys():parser.error('Unknown person ID')
        reconcile_live_people(state, people, active)
        handoff=consume(root,directory,state)
        if (args.review_round or args.evidence_only) and not handoff:parser.error('No fixed ChatGPT handoff')
        rejected=rejection_keys(root,args.live_ref)
        rejected.update(source_key(c.get('source')) for r in state['people'].values() for c in r['candidates'] if c.get('status')=='rejected' and c.get('source'))
        apply_rejections(state,rejected);recover_checkpoints(directory,state)
        if args.import_review:
            from media_pipeline.review import import_decisions
            import_decisions(root,directory,state,read(args.import_review))
        atomic(directory/'state.json',state)
        scanned=[];batch_result={'targetPeople':0,'processedPeople':0,'workers':args.workers}
        try:
            if args.manual_recrop_request:
                from tools.manual_recrop_from_commit import stage_manual_recrops
                scanned = stage_manual_recrops(root, directory, state, read(args.manual_recrop_request), run_id, active)
                batch_result = {'targetPeople': len(args.person_id) or len(read(args.manual_recrop_request)['items']),
                                'processedPeople': len(scanned), 'workers': 0, 'manualRecrop': True,
                                'sourceCommit': read(args.manual_recrop_request)['sourceCommit']}
                atomic(directory/'state.json', state)
            elif not args.render_only and not args.import_review:
                deadline=time.monotonic()+args.max_minutes*60
                if args.evidence_only:
                    for pid in handoff['personIds']:
                        row=state['people'][pid]
                        if row.get('chatgptReview',{}).get('decision')!='pending' or (args.person_id and pid not in args.person_id):continue
                        if len(scanned)>=args.limit or time.monotonic()>=deadline:break
                        scanned.append(pid);row['lastRunId']=run_id;row['lastRunNewCandidateIds']=[]
                        supplement(root,directory,row,people[pid],HTTP(attempts=1,timeout=8,budget=min(deadline,time.monotonic()+args.person_seconds)))
                        atomic(directory/'state.json',state)
                    batch_result.update({'targetPeople':len(scanned),'processedPeople':len(scanned)})
                else:
                    queue=select_people(state,people,handoff,args.limit,args.review_round,args.retry_failed,args.person_id)
                    selection_audit=requested_selection_audit(state,args.person_id,queue,args.retry_failed)
                    enriched={}
                    for pid in queue:
                        person=copy.deepcopy(people[pid]);review=state['people'][pid].get('chatgptReview',{})
                        person['reviewReason']=review.get('reason','');person['excludedCaptionNames']=merge_caption_exclusions(person, person['reviewReason'])
                        works=re.findall(r'《([^》]+)》',person['reviewReason'])+person.get('representativeWorks',[])
                        person['reviewSearchQuery']=person['name']+' '+' '.join(dict.fromkeys(works))+' portrait';enriched[pid]=person
                    records=read(args.official_sources,[]) if args.official_sources else []
                    registry={'curated':CuratedCommons(),'entity':EntityPortraits(allow_openverse=False),'commons':CommonsSearch(),'openverse':Openverse(),'wikimedia':Wikimedia(),'official':Official(records)}
                    scanned,batch_result=run_batch(root,directory,state,enriched,queue,[registry[n] for n in names],Cropper(root),rejected,active,run_id,deadline,args.workers,args.person_seconds,args.max_candidates)
                    batch_result['requestedPeople']=len(args.person_id)
                    batch_result['skippedRequested']=selection_audit
                    batch_result['unprocessedSelected']=[pid for pid in queue if pid not in scanned]
        finally:
            if protected(root)!=before:raise RuntimeError('Production files changed; do not commit')
            summary=report(root,directory,state,run_id,scanned)
            summary['batch']=batch_result
            atomic(directory/'runs'/run_id/'summary.json',summary)
            # Build pictures and contact sheets exactly once after collecting the batch.
            manifest=build_assets(root,directory,state,run_id,
                                  include_retained_sources=args.render_only,
                                  retained_source_person_ids=retained_source_targets(scanned, args.person_id),
                                  excluded_sources_by_person={pid: person.get('excludedPhotoSources', [])
                                                              for pid, person in people.items()})
            response={'schemaVersion':2,'sourceReviewSha256':(handoff or {}).get('sha256'),'releaseGate':'DRAFT_ONLY_NOT_PLAYABLE','runId':run_id,'reviewIndex':f'expansion-1500/pipeline/runs/{run_id}/review-index.json','visualAssetManifest':manifest['assetManifestPath'],'summary':summary,'visualPeople':manifest['peopleCount'],'visualPhotos':manifest['photoCount'],'batchPeople':scanned,'reviewPublicationPending':True,'items':[{'personId':pid,'name':state['people'][pid]['name'],'status':state['people'][pid]['status'],'newCandidateIds':state['people'][pid].get('lastRunNewCandidateIds',[]),'errors':state['people'][pid].get('lastErrors',[])} for pid in scanned]}
            atomic(directory/'codex-response/latest.json',response)
            print('BATCH SUMMARY',summary,flush=True);print('Visual assets:',manifest['assetManifestPath'],flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
