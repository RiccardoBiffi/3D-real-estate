#!/usr/bin/env python3
"""Check release invariants: identities, offline models, source provenance, no private chat/secrets."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from urllib.parse import urlparse

def baseline_models(commit, repository):
    """Read unchanged approvals from the exact previously deployed Git commit."""
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Baseline must be the full deployed commit SHA')
    catalog=json.loads(subprocess.check_output(['git','show',commit+':out/data/catalog.json'],cwd=repository,text=True))
    return {p['id']:p['model'] for p in catalog['properties'] if p['model']['status']=='ready'}

def validate(catalog,dist,work=None,baseline=None):
    errors=[];ids=[]
    for prop in catalog.get('properties',[]):
        pid=prop.get('id');ids.append(pid)
        if not isinstance(pid,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',pid):errors.append(f'Invalid property id {pid}')
        if prop.get('availability',{}).get('status') not in ('published','archived'):errors.append(f'{pid}: invalid availability')
        for url in prop.get('sourceUrls',[]):
            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password:errors.append(f'{pid}: unsafe source URL')
        for key in ('priceEur','areaHabitableM2','areaWalkableM2','areaCommercialM2','gardenM2','landM2'):
            value=prop.get('facts',{}).get(key)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(float,int)) or value<=0):errors.append(f'{pid}: invalid {key}')
        model=prop.get('model',{});ready=model.get('status')=='ready'
        if ready:
            for plan in model.get('sourcePlans',[]):
                parsed=urlparse(plan.get('url',''))
                if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password:errors.append(f'{pid}: unsafe floorplan URL')
            coverage=model.get('coverage','complete');missing=model.get('unrenderedVolumes',[])
            if coverage not in ('complete','partial','exterior_only'):errors.append(f'{pid}: invalid coverage')
            if coverage in ('partial','exterior_only') and not missing:errors.append(f'{pid}: partial model without omitted-volume disclosure')
            if coverage=='complete' and missing:errors.append(f'{pid}: complete model has omitted volumes')
            if not isinstance(missing,list) or not all(isinstance(v,str) and v.strip() for v in missing):errors.append(f'{pid}: invalid omitted-volume list')
            path=model.get('path','')
            if not re.fullmatch(r'modelli/[a-z0-9-]+\.html',path):errors.append(f'{pid}: unsafe model path');continue
            file=dist/path
            if not file.is_file():errors.append(f'{pid}: missing HTML')
            elif 'creation-finished' not in file.read_text():errors.append(f'{pid}: unfinished model')
            if not model.get('verifiedAt'):errors.append(f'{pid}: ready without verification date')
            if len(model.get('views',[]))<(1 if coverage=='exterior_only' else 2):errors.append(f'{pid}: missing declared views')
            if model.get('preview'):
                preview=model['preview']
                if not re.fullmatch(r'assets/[a-z0-9-]+\.jpg',preview) or not (dist/preview).is_file():errors.append(f'{pid}: invalid model preview')
            if work:
                # Carry forward only the exact model metadata AND HTML from an
                # already deployed commit; never manufacture fresh QA evidence.
                original=(baseline or {}).get(pid)
                if original==model and file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==original.get('artifactSha256'):
                    continue
                try:report=json.loads((work/'models'/(pid+'-review.json')).read_text())
                except (FileNotFoundError,json.JSONDecodeError):errors.append(f'{pid}: missing review evidence');continue
                required_qa=('staticPassed','browserPassed','geometryPassed')
                if coverage!='exterior_only':required_qa+=('orthographicPassed',)
                for key in required_qa:
                    if report.get('qa',{}).get(key) is not True:errors.append(f'{pid}: missing {key}')
                if report.get('fidelity',{}).get('passed') is not True or report.get('independentReview',{}).get('passed') is not True:errors.append(f'{pid}: missing independent geometry review')
                if file.is_file():
                    digest=hashlib.sha256(file.read_bytes()).hexdigest()
                    if digest!=model.get('artifactSha256'):errors.append(f'{pid}: public model digest mismatch')
                    if digest!=report.get('artifactSha256') or digest!=report.get('independentReview',{}).get('artifactSha256'):errors.append(f'{pid}: model changed after review')
        elif model.get('path') is not None:errors.append(f'{pid}: unapproved model exposed')
    if len(ids)!=len(set(ids)):errors.append('Duplicate property IDs')
    text=json.dumps(catalog,ensure_ascii=False)
    for marker in ('Bearer ','siwc_bypass','source_repository_credential','userMessage','agentMessage','/mnt/c/','/home/riccardo/','biffi.riccardo91@gmail.com','"chatFacts"','read_thread'):
        if marker in text:errors.append('Private/internal data in public catalog: '+marker)
    return errors
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('catalog');p.add_argument('--dist',required=True);p.add_argument('--work');p.add_argument('--expected',type=int);p.add_argument('--baseline-commit');a=p.parse_args();data=json.loads(Path(a.catalog).read_text());baseline=baseline_models(a.baseline_commit,Path(__file__).resolve().parents[1]) if a.baseline_commit else None;errors=validate(data,Path(a.dist),Path(a.work) if a.work else None,baseline)
    if a.expected is not None and len(data.get('properties',[]))!=a.expected:errors.append('Inventory count mismatch')
    print(json.dumps({'properties':len(data.get('properties',[])),'errors':errors,'passed':not errors},ensure_ascii=False,indent=2));raise SystemExit(bool(errors))
