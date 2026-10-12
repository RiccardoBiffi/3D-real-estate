#!/usr/bin/env python3
"""Build a public static directory containing only the catalog's approved assets."""
import argparse,hashlib,json,shutil,tempfile
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('catalog_validator',Path(__file__).with_name('validate-catalog.py'));validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
def stage(dist,out,work):
 catalog=json.loads((dist/'data/catalog.json').read_text());errors=validator.validate(catalog,dist,work)
 if errors:raise ValueError(errors)
 allowed={'index.html','app.js','styles.css','assets/favicon.svg','data/catalog.json'}
 models=[]
 for prop in catalog['properties']:
  model=prop['model']
  if model['status']=='ready':
   allowed.add(model['path'])
   if model.get('preview'):allowed.add(model['preview'])
   models.append({'id':prop['id'],'path':model['path'],'sha256':model['artifactSha256'],'coverage':model['coverage']})
 with tempfile.TemporaryDirectory(prefix='case-release-',dir=out.parent) as tmp:
  target=Path(tmp)
  for name in sorted(allowed):
   path=target/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dist/name,path)
  manifest={'schemaVersion':1,'catalogSha256':hashlib.sha256((target/'data/catalog.json').read_bytes()).hexdigest(),'models':models,'files':{name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in sorted(allowed)}}
  (target/'source-integrity.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
  if out.exists():shutil.rmtree(out)
  shutil.copytree(target,out)
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dist',required=True);p.add_argument('--out',required=True);p.add_argument('--work',required=True);a=p.parse_args();m=stage(Path(a.dist),Path(a.out),Path(a.work));print(json.dumps({'models':len(m['models']),'files':len(m['files']),'catalogSha256':m['catalogSha256']}))
