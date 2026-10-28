"""Bounded concurrent discovery; only the coordinator writes shared progress/reports."""
import concurrent.futures
import copy
import hashlib
import json
import time
from .core import atomic, read, process
from .sources import HTTP, now
from .rejection_pixels import rejected_fingerprints


def row_hash(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def recover_checkpoints(directory,state):
    recovered=[]
    for path in sorted((directory/'checkpoints').glob('*.json')):
        entry=read(path);pid=entry['personId'];row=state['people'].get(pid)
        if row is None or row['status'] in {'approved','published'}:continue
        if row_hash(row)!=entry['baseRowSha256']:continue
        updated=entry['row']
        if updated['personId']!=pid or updated['status'] in {'approved','published'}:raise ValueError('Unsafe worker checkpoint')
        if any(c.get('eligibleForLive') or c.get('status')=='approved' for c in updated['candidates']):raise ValueError('Worker cannot approve')
        updated['lastRunNewCandidateIds']=[cid for cid in updated.get('lastRunNewCandidateIds',[]) if any(c['id']==cid and c.get('status')=='pending_review' for c in updated['candidates'])]
        state['people'][pid]=updated;recovered.append(pid)
        atomic(directory/'state.json',state);path.unlink()
    return recovered


def merge_person(state,pid,updated,baseline):
    if row_hash(state['people'][pid])!=baseline:
        raise ValueError('Person changed while worker was searching')
    if updated['status'] in {'approved','published'}:raise ValueError('Worker cannot approve/publish')
    other_hashes={c.get(k) for other,row in state['people'].items() if other!=pid for c in row['candidates'] for k in ('gameSha256','originalSha256') if c.get(k)}
    for c in updated['candidates']:
        if c.get('eligibleForLive'):raise ValueError('Worker cannot make a live candidate')
        if c.get('status')=='pending_review' and any(c.get(k) in other_hashes for k in ('gameSha256','originalSha256') if c.get(k)):
            c['status']='automatic_duplicate_excluded'
            updated.setdefault('lastErrors',[]).append({'code':'cross_person_duplicate','message':'Image hash belongs to another person','candidateId':c['id']})
    if updated['status']=='pending_review' and not any(c.get('status')=='pending_review' for c in updated['candidates']):updated['status']='no_suitable_source'
    updated['lastRunNewCandidateIds']=[cid for cid in updated.get('lastRunNewCandidateIds',[]) if any(c['id']==cid and c.get('status')=='pending_review' for c in updated['candidates'])]
    state['people'][pid]=updated


def run_batch(root,directory,state,people,queue,providers,crop,rejected,active,run_id,deadline,workers=3,person_seconds=60,max_candidates=3,http_factory=HTTP):
    blocked_hosts={};scanned=[];started=time.monotonic()
    rejected_pixels=rejected_fingerprints(root,state)
    def worker(pid):
        row=copy.deepcopy(state['people'][pid]);baseline=row_hash(row);prior={c['id'] for c in row['candidates'] if c.get('gamePath')}
        row['lastRunId']=run_id;row['lastRunNewCandidateIds']=[];row['lastSearchRevision']=3
        checkpoint=directory/'checkpoints'/(pid+'.json')
        def save():atomic(checkpoint,{'personId':pid,'runId':run_id,'baseRowSha256':baseline,'row':row})
        budget=min(deadline,time.monotonic()+person_seconds)
        http=http_factory(attempts=1,timeout=8,interval=.5,budget=budget,blocked_hosts=blocked_hosts)
        try:
            process(people[pid],row,root,directory,providers,http,crop,rejected,max_candidates=max_candidates,max_attempts=18,deadline=budget,checkpoint=save,active=active,rejected_pixels=rejected_pixels)
        except Exception as exc:
            row['status']='download_failed';row['lastErrors']=[{'code':'worker_error','message':str(exc)[:400]}]
        row['lastRunNewCandidateIds']=[c['id'] for c in row['candidates'] if c.get('status')=='pending_review' and c.get('gamePath') and c['id'] not in prior]
        row['workerFinishedAt']=now();save()
        return pid,row,baseline,checkpoint
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        pending={};iterator=iter(queue)
        def submit():
            if time.monotonic()>=deadline:return False
            try:pid=next(iterator)
            except StopIteration:return False
            pending[pool.submit(worker,pid)]=pid;return True
        for _ in range(workers):submit()
        while pending:
            done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                pending.pop(future);pid,row,baseline,checkpoint=future.result()
                merge_person(state,pid,row,baseline);scanned.append(pid)
                atomic(directory/'state.json',state);checkpoint.unlink(missing_ok=True)
                print(f'[{len(scanned)}/{len(queue)}] {pid} {row["name"]}: {row["status"]}; new={len(row["lastRunNewCandidateIds"])}',flush=True)
                submit()
    return scanned,{'targetPeople':len(queue),'processedPeople':len(scanned),'workers':workers,'elapsedSeconds':round(time.monotonic()-started,2),'stoppedForBudget':len(scanned)<len(queue)}
