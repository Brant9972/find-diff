#!/usr/bin/env python3
"""Second phase: link already committed review images by immutable Git SHA."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import atomic,read
from media_pipeline.delivery import publish_links

p=argparse.ArgumentParser();p.add_argument('--asset-commit',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[2];directory=root/'expansion-1500/pipeline'
response=read(directory/'codex-response/latest.json');manifest=read(root/response['visualAssetManifest'])
public=publish_links(root,directory,manifest,args.asset_commit)
response['reviewPublicationPending']=False;response['visualAssetCommit']=args.asset_commit
response['publicReviewMarkdown']='https://github.com/Brant9972/find-diff/blob/automation/celebrity-photo-pipeline/singer/expansion-1500/pipeline/review-public/latest.md'
response['publicReviewJson']='https://raw.githubusercontent.com/Brant9972/find-diff/refs/heads/automation/celebrity-photo-pipeline/singer/expansion-1500/pipeline/review-public/latest.json'
response['publicVisualManifest']=public
atomic(directory/'codex-response/latest.json',response)
print('Published immutable review links for',manifest['peopleCount'],'people',manifest['photoCount'],'photos')
