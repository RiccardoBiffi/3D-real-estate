#!/usr/bin/env python3
"""Expand the public, source-specific geometry bundle; never approve a model."""
import hashlib,json,lzma,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
payload=(root/'model-authoring/batch-20261109.json.xz').read_bytes()
if hashlib.sha256(payload).hexdigest()!='36d97c59def1ebd5ea25f8fecf7a60a9792410923e950d36a4cc6d957f7731bf':raise ValueError('Authoring bundle integrity mismatch')
dec=lzma.LZMADecompressor(memlimit=256*1024*1024);raw=dec.decompress(payload,max_length=1024*1024)
if not dec.eof:raise ValueError('Authoring bundle exceeds limit')
items=json.loads(raw);catalog=json.loads((root/'out/data/catalog.json').read_text());known={p['id']:p for p in catalog['properties']}
if len(items)!=10 or len({x['id'] for x in items})!=10:raise ValueError('Unexpected authoring inventory')
for item in items:
 pid=item['id']
 if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',pid) or pid not in known:raise ValueError('Unknown property')
 if known[pid]['availability']['status']!='published' or known[pid].get('model',{}).get('status')=='ready':raise ValueError('Refusing to overwrite an approved or archived model')
 if not item.get('sources') or not item.get('unrenderedVolumes'):raise ValueError('Missing source or scope evidence')
 (root/'models-source').mkdir(exist_ok=True)
 (root/'models-source'/(pid+'.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n')
print('Expanded 10 model drafts; no catalog status changed.')
