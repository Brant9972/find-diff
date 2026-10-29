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
from media_pipeline.sources import CommonsSearch,EntityPortraits,Official,Openverse,Wikimedia,norm,source_key,HTTP
from media_pipeline.batch import SEARCH_REVISION,recover_checkpoints,run_batch
from media_pipeline.evidence import supplement
from media_pipeline.review import report
from media_pipeline.delivery import build_assets


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
    if not names or set(names)-{'entity','commons','openverse','wikimedia','official'}:parser.error('Unknown/empty provider')
    root=Path(__file__).resolve().parents[1];directory=root/'expansion-1500/pipeline';before=protected(root)
    run_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    with lock(directory):
        active=live_people(root,args.live_ref);state=initialise(root,directory,active=active)
        people={p['plannedQuestionId']:p for p in read(root/'expansion-1500/release-plan-20261028.json')['selectedNew']}
        if set(args.person_id)-people.keys():parser.error('Unknown person ID')
        active_names={norm(q['name']) for q in active.values()}
        for pid,row in state['people'].items():
            if pid in active or norm(row['name']) in active_names:row['status']='published'
            elif people[pid].get('duplicateExistingCanonicalId') in active:row['status']='duplicate_existing'
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
                    enriched={}
                    for pid in queue:
                        person=copy.deepcopy(people[pid]);review=state['people'][pid].get('chatgptReview',{})
                        person['reviewReason']=review.get('reason','');person['excludedCaptionNames']=re.findall(r'涉及([^；，。 ]+)',person['reviewReason'])
                        works=re.findall(r'《([^》]+)》',person['reviewReason'])+person.get('representativeWorks',[])
                        person['reviewSearchQuery']=person['name']+' '+' '.join(dict.fromkeys(works))+' portrait';enriched[pid]=person
                    records=read(args.official_sources,[]) if args.official_sources else []
                    registry={'entity':EntityPortraits(),'commons':CommonsSearch(),'openverse':Openverse(),'wikimedia':Wikimedia(),'official':Official(records)}
                    scanned,batch_result=run_batch(root,directory,state,enriched,queue,[registry[n] for n in names],Cropper(root),rejected,active,run_id,deadline,args.workers,args.person_seconds,args.max_candidates)
        finally:
            if protected(root)!=before:raise RuntimeError('Production files changed; do not commit')
            summary=report(root,directory,state,run_id,scanned)
            summary['batch']=batch_result
            atomic(directory/'runs'/run_id/'summary.json',summary)
            # Build pictures and contact sheets exactly once after collecting the batch.
            manifest=build_assets(root,directory,state,run_id, include_retained_sources=args.render_only)
            response={'schemaVersion':2,'sourceReviewSha256':(handoff or {}).get('sha256'),'releaseGate':'DRAFT_ONLY_NOT_PLAYABLE','runId':run_id,'reviewIndex':f'expansion-1500/pipeline/runs/{run_id}/review-index.json','visualAssetManifest':manifest['assetManifestPath'],'summary':summary,'visualPeople':manifest['peopleCount'],'visualPhotos':manifest['photoCount'],'batchPeople':scanned,'reviewPublicationPending':True,'items':[{'personId':pid,'name':state['people'][pid]['name'],'status':state['people'][pid]['status'],'newCandidateIds':state['people'][pid].get('lastRunNewCandidateIds',[]),'errors':state['people'][pid].get('lastErrors',[])} for pid in scanned]}
            atomic(directory/'codex-response/latest.json',response)
            print('BATCH SUMMARY',summary,flush=True);print('Visual assets:',manifest['assetManifestPath'],flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
