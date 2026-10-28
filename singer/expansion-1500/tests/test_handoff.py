import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import atomic, valid_reveal
from media_pipeline.handoff import consume
from media_pipeline.evidence import previews, supplement
from media_pipeline.sources import SourceError

REVEAL={k:[.08,.2,.92,y] for k,y in [('eyes',.4),('nose',.55),('mouth',.7),('chin',.9)]}
REVEAL['full']=[0,0,1,1]


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'singer';self.directory=self.root/'expansion-1500/pipeline'
        image=self.root/'expansion-1500/review_photos/t1.jpg';image.parent.mkdir(parents=True);Image.new('RGB',(600,720),'#b98877').save(image)
        self.candidate={'id':'legacy-t1','gamePath':str(image.relative_to(self.root)),'gameSha256':hashlib.sha256(image.read_bytes()).hexdigest(),'status':'legacy_requires_review','reveal':REVEAL,'source':'https://commons.wikimedia.org/wiki/File:Person.jpg','eligibleForLive':False,'rightsStatus':'needs_review'}
        self.state={'schemaVersion':2,'people':{'t1':{'personId':'t1','name':'測試人物','status':'pending_review','candidates':[self.candidate]}}}
        self.document={'schemaVersion':1,'releaseGate':'DRAFT_ONLY_NOT_PLAYABLE','sourceCommit':'fixture','decisions':[{'personId':'t1','candidateId':'legacy-t1','gameSha256':self.candidate['gameSha256'],'decision':'pending','reason':'Need source and reveal evidence'}]}
    def tearDown(self):self.temp.cleanup()
    def write(self):atomic(self.directory/'chatgpt-review/latest.json',self.document)
    def test_fixed_handoff_is_idempotent_and_preserves_pending(self):
        self.write();result=consume(self.root,self.directory,self.state);again=consume(self.root,self.directory,self.state)
        self.assertEqual(result,again);self.assertEqual(len(self.candidate['externalReviewHistory']),1)
        self.assertEqual(self.candidate['status'],'pending_evidence');self.assertFalse(self.candidate['eligibleForLive'])
    def test_reject_cannot_be_lost_or_reapproved_automatically(self):
        self.document['decisions'][0]['decision']='reject';self.write();consume(self.root,self.directory,self.state)
        self.assertEqual(self.state['people']['t1']['status'],'rejected')
        self.document['decisions'][0]['decision']='approved';self.write()
        with self.assertRaises(ValueError):consume(self.root,self.directory,self.state)
        self.assertEqual(self.candidate['status'],'rejected')
    def test_stale_hash_and_duplicate_batch_are_atomic(self):
        before=copy.deepcopy(self.state);self.document['decisions'][0]['gameSha256']='stale';self.write()
        with self.assertRaises(ValueError):consume(self.root,self.directory,self.state)
        self.assertEqual(before,self.state)
        self.document['decisions'][0]['gameSha256']=self.candidate['gameSha256'];self.document['decisions']*=2;self.write()
        with self.assertRaises(ValueError):consume(self.root,self.directory,self.state)
        self.assertEqual(before,self.state)
    def test_previews_use_exact_saved_pixels_and_do_not_change_photo(self):
        before=(self.root/self.candidate['gamePath']).read_bytes();previews(self.root,self.directory,self.candidate)
        self.assertEqual(len(self.candidate['stagePreviews']),5)
        for key,path in self.candidate['stagePreviews'].items():
            with Image.open(self.root/path) as im:
                self.assertEqual(im.size,(600,720))
                if key=='eyes':self.assertEqual(im.getpixel((0,0)),(23,21,31))
        self.assertEqual(before,(self.root/self.candidate['gamePath']).read_bytes())
    def test_network_failure_keeps_pending_and_generates_evidence(self):
        self.write();consume(self.root,self.directory,self.state)
        class Denied:
            def json(self,*a,**k):raise SourceError('proxy_access_denied','fixture denial')
        supplement(self.root,self.directory,self.state['people']['t1'],{'name':'測試人物'},Denied())
        self.assertEqual(self.state['people']['t1']['status'],'pending_review')
        self.assertEqual(self.candidate['evidenceSupplement']['errors'][0]['code'],'proxy_access_denied')
        self.assertEqual(len(self.candidate['stagePreviews']),5)
    def test_source_enrichment_is_evidence_and_never_approval(self):
        self.write();consume(self.root,self.directory,self.state)
        class Metadata:
            def json(self,url,**kw):
                if 'wikipedia' in url:return {'query':{'pages':[{'fullurl':'https://zh.wikipedia.org/wiki/測試人物','extract':'測試人物為演員'}]}}
                return {'query':{'pages':[{'imageinfo':[{'url':'https://upload.wikimedia.org/a.jpg','width':1800,'height':2100,'extmetadata':{k:{'value':v} for k,v in {'Artist':'Photographer','LicenseShortName':'CC BY 4.0','LicenseUrl':'https://creativecommons.org/licenses/by/4.0/','ImageDescription':'測試人物'}.items()}}]}]}}
            def get(self,url):raise SourceError('network_error','Image download failed')
        supplement(self.root,self.directory,self.state['people']['t1'],{'name':'測試人物'},Metadata())
        self.assertEqual(self.candidate['rightsStatus'],'open_license_metadata')
        self.assertFalse(self.candidate['eligibleForLive'])
        self.assertFalse(self.candidate['evidenceSupplement']['rightsHumanVerified'])
        self.assertTrue(self.candidate['evidenceSupplement']['sourceMetadata']['width'])

if __name__=='__main__':unittest.main()
