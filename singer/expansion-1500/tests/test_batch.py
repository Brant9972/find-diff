import copy
import importlib.util
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media_pipeline.batch import run_batch,merge_person,row_hash,recover_checkpoints
from media_pipeline.core import atomic


class BatchTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'singer';self.directory=self.root/'expansion-1500/pipeline'
        self.state={'schemaVersion':2,'people':{f'p{i}':{'personId':f'p{i}','name':f'Person {i}','status':'not_started','attempts':0,'candidates':[]} for i in range(40)}}
        atomic(self.directory/'state.json',self.state)
    def tearDown(self):self.temp.cleanup()
    def test_forty_people_bounded_parallel_single_writer_and_failure_isolation(self):
        active=0;peak=0;guard=threading.Lock()
        def fake(person,row,*args,**kwargs):
            nonlocal active,peak
            with guard:active+=1;peak=max(peak,active)
            try:
                time.sleep(.01)
                if row['personId']=='p7':raise ValueError('One person failed')
                row['status']='pending_review';row['candidates'].append({'id':row['personId']+'-photo','status':'pending_review','gamePath':'fixture.jpg','gameSha256':row['personId'],'eligibleForLive':False});kwargs['checkpoint']()
            finally:
                with guard:active-=1
        with patch('media_pipeline.batch.process',fake):
            scanned,result=run_batch(self.root,self.directory,self.state,{p:{} for p in self.state['people']},list(self.state['people']),[],None,set(),{},'test-batch',time.monotonic()+10,workers=3)
        self.assertEqual(len(scanned),40);self.assertEqual(len(set(scanned)),40);self.assertGreater(peak,1);self.assertLessEqual(peak,3)
        self.assertEqual(self.state['people']['p7']['status'],'download_failed')
        stored=json.loads((self.directory/'state.json').read_text());self.assertEqual(stored,self.state)
        self.assertFalse(list((self.directory/'checkpoints').glob('*.json')))
    def test_resume_partial_checkpoint_only_when_base_unchanged(self):
        row=self.state['people']['p0'];updated=copy.deepcopy(row);updated['status']='searching';updated['attempts']=1
        atomic(self.directory/'checkpoints/p0.json',{'personId':'p0','baseRowSha256':row_hash(row),'row':updated})
        self.assertEqual(recover_checkpoints(self.directory,self.state),['p0']);self.assertEqual(self.state['people']['p0']['attempts'],1)
        atomic(self.directory/'checkpoints/p0.json',{'personId':'p0','baseRowSha256':'stale','row':row})
        self.assertEqual(recover_checkpoints(self.directory,self.state),[])
    def test_cross_person_duplicate_not_counted_as_new_photo(self):
        self.state['people']['p1']['candidates']=[{'id':'existing','gameSha256':'same','eligibleForLive':False}]
        baseline=row_hash(self.state['people']['p0']);row=copy.deepcopy(self.state['people']['p0']);row['status']='pending_review';row['candidates']=[{'id':'new','status':'pending_review','gameSha256':'same','eligibleForLive':False}];row['lastRunNewCandidateIds']=['new']
        merge_person(self.state,'p0',row,baseline)
        self.assertEqual(row['candidates'][0]['status'],'automatic_duplicate_excluded');self.assertEqual(row['lastRunNewCandidateIds'],[])
    def test_worker_cannot_introduce_approval_or_overwrite_changed_row(self):
        baseline=row_hash(self.state['people']['p0']);row=copy.deepcopy(self.state['people']['p0']);row['status']='approved'
        with self.assertRaises(ValueError):merge_person(self.state,'p0',row,baseline)
        self.state['people']['p0']['attempts']=9;row['status']='not_started'
        with self.assertRaises(ValueError):merge_person(self.state,'p0',row,baseline)

if __name__=='__main__':unittest.main()
