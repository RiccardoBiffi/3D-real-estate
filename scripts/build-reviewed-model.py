#!/usr/bin/env python3
"""Deterministically build evidence-specific geometry with the existing offline renderer.
Only the licensed renderer and controls are reused, never another house's geometry.
"""
import argparse, json, re, hashlib, html
from pathlib import Path

def build(source, output, reference):
    data=json.loads(source.read_text())
    if not data.get('levels') or not data.get('creationStarted') or not data.get('sources'):
        raise ValueError('Missing property geometry, timestamp or inspected evidence')
    old=reference.read_text();scripts=re.findall(r'<script[^>]*>([\s\S]*?)</script>',old)
    if len(scripts)!=2 or not scripts[0].startswith('window.MODEL_DATA='):
        raise ValueError('Unexpected renderer structure')
    runtime=scripts[1]
    marker='var di=[{label:"Esterno dal giardino",level:null},{label:"Terrazze e mansarda \\u2014 esterno",level:null}];'
    if runtime.count(marker)!=1:raise ValueError('Unexpected reference view table')
    runtime=runtime.replace(marker,'var di=Ce.views||[{label:"Esterno",level:null},...Ce.levels.map((l,i)=>({label:l.label,level:i})).reverse()];')
    marker='ge.update()}function lc()'
    if runtime.count(marker)!=1:raise ValueError('Unexpected camera initializer')
    runtime=runtime.replace(marker,'ge.update();if(di[Ln].camera){let v=di[Ln].camera;ge.target.fromArray(v.target||ge.target.toArray());ke.position.copy(ge.target).add(new P(Math.sin(v.yaw)*Math.cos(v.pitch)*v.distance,Math.sin(v.pitch)*v.distance,Math.cos(v.yaw)*Math.cos(v.pitch)*v.distance));ge.update();}}function lc()')
    if 'Gianelli' in runtime:raise ValueError('Property identifier leaked into generic renderer')
    lm=re.search(r'(<!-- Three.js license:[\s\S]*?-->)',old)
    license_text=lm.group(1) if lm else '<!-- Three.js MIT; copyright Three.js authors. License retained in renderer bundle. -->'
    esc=lambda x:html.escape(str(x),quote=True)
    metas=''.join(f'<meta name="{k}" content="{esc(v)}">' for k,v in [('creation-started',data['creationStarted']),('reconstruction-skill-version','1.0.0'),('coverage',data['coverage']),('unrenderedVolumes',json.dumps(data['unrenderedVolumes'],ensure_ascii=False))])
    if data.get('creationFinished'):metas+=f'<meta name="creation-finished" content="{esc(data["creationFinished"])}">'
    safe=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    page=f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{metas}<title>{esc(data['title'])}</title><link rel="icon" href="data:,"><style>html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#ebe9e2}}canvas{{display:block;width:100%;height:100%;touch-action:none;outline:none}}</style></head><body><canvas aria-label="Ricostruzione 3D di {esc(data['title'])}. Trascina per ruotare, rotella per zoom, tasto destro per pan. R cambia vista, T vista dall'alto, Home ripristina." tabindex="0"></canvas><script>window.MODEL_DATA={safe};</script><script>{runtime}</script>{license_text}</body></html>'''
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(page)
    return {'path':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'viewCount':len(data.get('views',[])) or len(data['levels'])+1,'bytes':output.stat().st_size}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--reference',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.source,a.output,a.reference)))
