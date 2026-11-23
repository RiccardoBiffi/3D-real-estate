#!/usr/bin/env python3
"""Build a public static directory containing only the catalog's approved assets."""
import argparse,hashlib,json,re,shutil,tempfile
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('catalog_validator',Path(__file__).with_name('validate-catalog.py'));validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)

def collection_files(catalog, dist):
 collection=catalog.get('reconstructionCollection')
 if not collection:
  return set()
 directory=collection['directory']
 if not re.fullmatch(r'ricostruzioni/\d{4}-\d{2}-\d{2}',directory):
  raise ValueError('Invalid reconstruction collection directory')
 collection_index=json.loads((dist/directory/'fonti-e-copertura.json').read_text())
 names={'index.html','fonti-e-copertura.json','verifica-annunci.csv','verifiche/risultati.json','verifiche/catalogo.json'}
 approved={p['id'] for p in catalog['properties'] if p['model']['status']=='ready'}
 for house in collection_index['properties']:
  pid=house['id']
  if pid not in approved:
   raise ValueError(f'{pid}: collection entry has no approved model')
  for source in [*house['planFiles'], *house['thumbs']]:
   name=source['path']
   if not re.fullmatch(r'fonti/'+re.escape(pid)+r'/[\w.-]+\.(jpg|jpeg|png|webp|pdf)',name,re.I):
    raise ValueError(f'{pid}: invalid source asset {name}')
   names.add(name)
  for comparison in house['comparisons']:
   name=comparison['file']
   if not re.fullmatch(re.escape(pid)+r'[-\w.]*\.(jpg|jpeg|png|webp)',name,re.I):
    raise ValueError(f'{pid}: invalid comparison asset {name}')
   names.add('confronti/'+name)
 return {f'{directory}/{name}' for name in names}

def stage(dist,out,work,baseline=None):
 catalog=json.loads((dist/'data/catalog.json').read_text());errors=validator.validate(catalog,dist,work,baseline)
 if errors:raise ValueError(errors)
 allowed={'index.html','app.js','styles.css','assets/favicon.svg','data/catalog.json'}
 allowed.update(collection_files(catalog,dist))
 models=[]
 for prop in catalog['properties']:
  model=prop['model']
  if model['status']=='ready':
   allowed.add(model['path'])
   if model.get('preview'):allowed.add(model['preview'])
   for alias in model.get('previewAliases',[]):
    if not re.fullmatch(r'assets/[a-z0-9-]+\.jpg',alias):
     raise ValueError(f'Invalid public preview alias {alias}')
    allowed.add(alias)
   models.append({'id':prop['id'],'path':model['path'],'sha256':model['artifactSha256'],'coverage':model['coverage']})
 with tempfile.TemporaryDirectory(prefix='case-release-',dir=out.parent) as tmp:
  target=Path(tmp)/'public'
  target.mkdir()
  for name in sorted(allowed):
   path=target/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dist/name,path)
  manifest={'schemaVersion':1,'catalogSha256':hashlib.sha256((target/'data/catalog.json').read_bytes()).hexdigest(),'models':models,'files':{name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in sorted(allowed)}}
  (target/'source-integrity.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
  previous=Path(tmp)/'previous'
  if out.exists():out.rename(previous)
  try:
   target.rename(out)
  except OSError:
   if previous.exists():previous.rename(out)
   raise
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dist',required=True);p.add_argument('--out',required=True);p.add_argument('--work',required=True);p.add_argument('--baseline-commit');a=p.parse_args();baseline=validator.baseline_models(a.baseline_commit,Path(__file__).resolve().parents[1]) if a.baseline_commit else None;m=stage(Path(a.dist),Path(a.out),Path(a.work),baseline);print(json.dumps({'models':len(m['models']),'files':len(m['files']),'catalogSha256':m['catalogSha256']}))
