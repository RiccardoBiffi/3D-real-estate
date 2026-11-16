#!/usr/bin/env python3
"""Add reviewed models without rebuilding or rolling back the live property data."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

spec=importlib.util.spec_from_file_location('validator',Path(__file__).with_name('validate-catalog.py'))
validator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

class Metadata(HTMLParser):
    def __init__(self,text):
        super().__init__();self.values={};self.feed(text)
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='meta' and attrs.get('name'):
            self.values[attrs['name']]=attrs.get('content','')

def integrate(catalog,dist,work,baseline):
    result=copy.deepcopy(catalog);added=[]
    for prop in result['properties']:
        if prop['availability']['status']!='published':
            continue
        pid=prop['id'];path=work/'models'/(pid+'-review.json')
        if not path.is_file():
            continue
        report=json.loads(path.read_text());independent=report.get('independentReview',{})
        if report.get('status')!='ready' or independent.get('passed') is not True:
            continue
        if report.get('id',pid)!=pid:
            raise ValueError(f'{pid}: review belongs to another property')
        model={k:copy.deepcopy(report.get(k)) for k in (
            'status','path','views','coverage','unrenderedVolumes','notes','verifiedAt','artifactSha256')}
        model['notes']=copy.deepcopy(report.get('notes') or report.get('limitations') or [])
        model['views']=[{'id':f'view-{i}','label':v} if isinstance(v,str) else v for i,v in enumerate(model['views'] or [])]
        if any(not isinstance(v,dict) or not isinstance(v.get('label'),str) or not v['label'].strip() for v in model['views']):
            raise ValueError(f'{pid}: every public view requires a label')
        model['sourcePlans']=[{'url':p.get('url'),'label':p.get('label') or f'Planimetria {i+1}'} for i,p in enumerate(report.get('sourcePlans',[]))]
        preview='assets/'+pid+'.jpg'
        if (dist/preview).is_file():
            model['preview']=preview
        # Validate paths and evidence before opening an artifact supplied by a review.
        candidate={**prop,'model':model}
        errors=validator.validate({'properties':[candidate]},dist,work)
        if errors:
            raise ValueError(errors)
        meta=Metadata((dist/model['path']).read_text()).values
        if meta.get('coverage')!=model['coverage']:
            raise ValueError(f'{pid}: HTML and catalog coverage disagree')
        if json.loads(meta.get('unrenderedVolumes','[]'))!=model['unrenderedVolumes']:
            raise ValueError(f'{pid}: HTML and catalog omitted volumes disagree')
        started=datetime.fromisoformat(meta['creation-started'])
        finished=datetime.fromisoformat(meta['creation-finished'])
        if started.tzinfo is None or finished.tzinfo is None or finished<started:
            raise ValueError(f'{pid}: invalid reconstruction timestamps')
        if prop['model']==model:
            continue
        prop['model']=model;added.append(pid)
    errors=validator.validate(result,dist,work,baseline)
    if errors:
        raise ValueError(errors)
    if added:
        result['updatedAt']=datetime.now(ZoneInfo('Europe/Rome')).isoformat()
    return result,added

def atomic_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    os.replace(temporary,path)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--dist',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--baseline-commit',required=True);a=p.parse_args()
    baseline=validator.baseline_models(a.baseline_commit,Path(__file__).resolve().parents[1])
    old=json.loads(a.catalog.read_text());updated,added=integrate(old,a.dist,a.work,baseline)
    if added:
        atomic_json(a.catalog,updated)
    print(json.dumps({'added':added,'properties':len(updated['properties']),
        'ready':sum(p['model']['status']=='ready' for p in updated['properties']),
        'publishedWithoutModel':sum(p['availability']['status']=='published' and p['model']['status']!='ready' for p in updated['properties'])}))
