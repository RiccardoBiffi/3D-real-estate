#!/usr/bin/env python3
"""Record deployment receipts; a failed attempt never replaces the last valid release."""
import argparse,copy,json,os
from pathlib import Path

def record(previous,candidate,receipt):
    state=copy.deepcopy(previous)
    attempt={'commitSha':candidate['commitSha'],'catalogSha256':candidate['catalogSha256'],'versionId':receipt.get('version_id'),'deploymentId':receipt.get('id'),'status':receipt.get('status'),'failureMessage':receipt.get('failure_message')}
    state['lastAttempt']=attempt
    if receipt.get('status')=='succeeded':
        if not receipt.get('version_id') or not receipt.get('id') or not receipt.get('url'):raise ValueError('Successful deployment requires native version/deployment IDs and URL')
        if not candidate.get('checksPassed') or not candidate.get('deployedFilesMatched'):raise ValueError('Do not accept a release before deployed bytes and local checks match')
        state['lastSuccessful']={**attempt,'url':receipt['url'],'verifiedAt':candidate.get('verifiedAt')}
    return state

def meaningful_changes(before,after):
    old={p['id']:p for p in before.get('properties',[])};changes=[]
    for prop in after.get('properties',[]):
        pid=prop['id'];previous=old.get(pid)
        if previous is None:changes.append({'id':pid,'kind':'new'});continue
        if previous.get('availability',{}).get('status')!=prop.get('availability',{}).get('status'):changes.append({'id':pid,'kind':'availability'})
        if previous.get('facts')!=prop.get('facts'):changes.append({'id':pid,'kind':'facts'})
        # Check dates alone should never produce a notification.
        for key in ('status','path','notes','views','coverage','unrenderedVolumes','artifactSha256'):
            if previous.get('model',{}).get(key)!=prop.get('model',{}).get(key):changes.append({'id':pid,'kind':'model'});break
    return changes

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',required=True);p.add_argument('--candidate',required=True);p.add_argument('--receipt',required=True);a=p.parse_args();path=Path(a.state)
    previous=json.loads(path.read_text()) if path.exists() else {};result=record(previous,json.loads(Path(a.candidate).read_text()),json.loads(Path(a.receipt).read_text()));tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path);print(json.dumps({'lastAttemptStatus':result['lastAttempt']['status'],'lastSuccessfulUnchanged':previous.get('lastSuccessful')==result.get('lastSuccessful')}))
