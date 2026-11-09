#!/usr/bin/env python3
"""Collect exact galleries without collapsing photos that share a size filename.
Evidence is exported for visual review only; this does not approve models.
"""
import argparse, hashlib, html, importlib.util, json, re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capture_base',root/'scripts/capture-model-sources.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
EXTRA={
 'chiampore-43a':['https://www.trovacasa.it/annunci/ts-tc-79841-72872497'],
 'borgo-refosco':['https://www.trovacasa.it/annunci/ts-tc-88049-68211776'],
 'via-dell-hermada':['https://www.trovacasa.it/annunci/ts-tc-36387-69859642'],
 'opicina-trifamiliare-via-basovizza':['https://www.trovacasa.it/annunci/ts-tc-36387-69859640']
}
KNOWN={'via-gianelli-18','via-degli-alpini-opicina','duino-le-vigne','via-dei-mulini-44','via-del-panorama-4','vanisella-1-a'}

def candidates(text,parser,url):
    clean=html.unescape(text).replace('\\/','/').replace('\\u002F','/').replace('\\u0026','&')
    for m in re.finditer(r'https://[^\s<>\"\'\\]+\.(?:jpg|jpeg|png|webp|pdf)(?:\?[^\s<>\"\'\\]*)?',clean,re.I):
        parser.add(m.group(0),'','Embedded media reference')
    chosen={}
    for item in parser.media:
        u=item['url'];parts=urlsplit(u);path=parts.path
        if re.search(r'/team/|team_member|public/images|og-default|/brand/|agenziaentrate|dt.mef',u,re.I):continue
        if '/foto/att' in path:
            key=path.split('/')[2]
            match=re.search(r'/(\d+)',path.split(key)[1]);score=int(match.group(1)) if match else 0
            if '-ai' in path:item['artificiallyModified']=True
        elif 'medialabtc.it' in u:
            if '/estates/' not in path:continue
            match=re.search(r'/images/(\d+)/',path);key=match.group(1) if match else path
            score=100 if '/gallery.' in path else 50 if '/detail.' in path else 10
        elif '/plan/' in path or 'planimetr' in path.lower():
            key=re.sub(r'/(?:m|s|l|xxl)\.(?:jpg|png)$','',path);score=5000
        elif '/image/' in path:
            key=path.split('/image/')[1].split('/')[0];score=100 if '/xxl' in path else 50
        else:
            key=re.sub(r'-\d{2,4}x\d{2,4}(?=\.)','',path);score=30 if not re.search(r'-\d+x\d+\.',path) else 10
        if parts.hostname and 'tirabora.it' in parts.hostname:
            if '/immobili/2070/' not in path and '/planimetrie/' not in path:continue
        item['priority']=score
        if key not in chosen or score>chosen[key]['priority']:chosen[key]=item
    return sorted(chosen.values(),key=lambda x:-x['priority'])

def process(prop,out):
    pid=prop['id'];d=out/pid;d.mkdir(parents=True,exist_ok=True)
    report={'id':pid,'title':prop['title'],'startedAt':datetime.now(timezone.utc).isoformat(),'pages':[],'media':[],'limitations':['Downloaded candidates need visual identity and geometry review; related images must not be used.']}
    urls=EXTRA.get(pid,[]) or [u for u in prop['sourceUrls'] if not any(h in u for h in ('www.immobiliare.it','www.idealista.it','www.casa.it'))]
    seen=set()
    for url in urls:
        page={'url':url,'readAt':datetime.now(timezone.utc).isoformat()}
        try:
            raw,mime=r.download(url);text=raw.decode('utf-8','replace');p=r.SourceHTML(url);p.feed(text)
            title=re.search(r'<title[^>]*>(.*?)</title>',text,re.S|re.I)
            page.update({'title':html.unescape(title.group(1)) if title else '', 'readable':True,'sha256':hashlib.sha256(raw).hexdigest()})
            if re.search(r'access denied|captcha|just a moment',page['title'],re.I):raise ValueError('Challenge not bypassed')
            page['text']='\n'.join(p.text)[:30000]
            for item in candidates(text,p,url)[:90]:
                if len(report['media'])>=64:break
                try:
                    binary,m=r.download(item['url'],18*1024*1024)
                    if m not in ('image/jpeg','image/png','image/webp','application/pdf'):continue
                    sha=hashlib.sha256(binary).hexdigest()
                    if sha in seen:continue
                    seen.add(sha);ext={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','application/pdf':'.pdf'}[m]
                    name=f'{len(report["media"]):02d}-{sha[:12]}{ext}';(d/name).write_bytes(binary)
                    item.update({'file':name,'mimeType':m,'sha256':sha,'pageUrl':url,'identityVerified':False})
                    report['media'].append(item)
                except Exception as exc:item['downloadError']=str(exc)[:160]
        except Exception as exc:page['error']=str(exc)[:160]
        report['pages'].append(page)
    report['finishedAt']=datetime.now(timezone.utc).isoformat();(d/'evidence.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    result={'id':pid,'mediaCount':len(report['media']),'readablePages':sum(p.get('readable',False) for p in report['pages'])};print(json.dumps(result),flush=True);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    c=json.loads((root/'out/data/catalog.json').read_text());props=[p for p in c['properties'] if p['id'] in KNOWN or p['id'] in EXTRA]
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda p:process(p,out),props))
    (out/'inventory.json').write_text(json.dumps({'checkedAt':datetime.now(timezone.utc).isoformat(),'properties':results,'newModelsCreated':0},indent=2)+'\n')
if __name__=='__main__':main()
