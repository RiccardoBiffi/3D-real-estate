#!/usr/bin/env python3
"""Acquire public evidence for missing models; never infer geometry or approve QA.
Output belongs in temporary review storage, not the public website or Git tree.
"""
from __future__ import annotations
import argparse, hashlib, html, json, re, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler

blocked = set(); lock = threading.Lock(); total_bytes = 0
MAX_TOTAL = 350 * 1024 * 1024

class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urlsplit(req.full_url), urlsplit(newurl)
        if new.scheme != 'https' or new.hostname != old.hostname or re.search(r'(?:login|signin|captcha|challenge)',new.path,re.I):
            raise ValueError('Redirect requires separate review; not followed')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download(url, limit=8*1024*1024):
    global total_bytes
    u=urlsplit(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password:
        raise ValueError('Unsafe URL')
    if any(re.search(r'token|signature|credential|authorization|secret',k,re.I) for k in parse_qs(u.query)):
        raise ValueError('Credential-bearing URL not persisted')
    with lock:
        if u.hostname in blocked: raise ValueError('Host access restriction already encountered')
        if total_bytes > MAX_TOTAL: raise ValueError('Review download budget reached')
    try:
        req=Request(url,headers={'User-Agent':'Case-in-3D-source-review/1.0','Accept':'text/html,image/*,application/pdf;q=0.9,*/*;q=0.5'})
        with build_opener(SafeRedirect()).open(req,timeout=18) as response:
            data=response.read(limit+1); kind=response.headers.get('Content-Type','').split(';')[0]
    except HTTPError as exc:
        if exc.code in (401,403,429):
            with lock: blocked.add(u.hostname)
        raise ValueError('HTTP '+str(exc.code)) from None
    if len(data)>limit: raise ValueError('Source exceeds review file limit')
    with lock: total_bytes+=len(data)
    return data,kind

class SourceHTML(HTMLParser):
    def __init__(self,base):
        super().__init__();self.base=base;self.media=[];self.text=[];self.skip=0;self.title=False;self.title_parts=[]
    def add(self,value,caption='',where='HTML'):
        if not value:return
        value=html.unescape(value).strip().replace('\\/','/')
        if value.startswith('//'):value='https:'+value
        value=urljoin(self.base,value)
        if value.startswith('https://') and re.search(r'\.(?:jpg|jpeg|png|webp|pdf)(?:\?|$)',value,re.I):
            if not re.search(r'(?:logo|favicon|sprite|placeholder|avatar|brandmark)',value,re.I):
                self.media.append({'url':value,'caption':caption[:250],'discoveredIn':where,'identityVerified':False})
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style','noscript'):self.skip+=1
        if tag=='title':self.title=True
        if tag in ('img','source','a'):
            for key in ('src','data-src','data-lazy-src','href','data-large-file','data-full-url','data-orig-file'):
                self.add(a.get(key),a.get('alt',a.get('title','')),tag+'.'+key)
            for key in ('srcset','data-srcset'):
                if a.get(key):
                    for x in a[key].split(','): self.add(x.strip().split(' ')[0],a.get('alt',''),tag+'.'+key)
        if tag=='meta' and a.get('property')=='og:image':self.add(a.get('content'),'Listing cover','og:image')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript') and self.skip:self.skip-=1
        if tag=='title':self.title=False
    def handle_data(self,data):
        if self.title:self.title_parts.append(data)
        if not self.skip and data.strip():self.text.append(data.strip())

def collect_urls(text,parser):
    clean=html.unescape(text).replace('\\/','/').replace('\\u002F','/').replace('\\u0026','&')
    for m in re.finditer(r'https://[^\s<>\"\'\\]+\.(?:jpg|jpeg|png|webp|pdf)(?:\?[^\s<>\"\'\\]*)?',clean,re.I):
        parser.add(m.group(0),'','Embedded URL, needs visual identity review')
    chosen={}
    for item in parser.media:
        u=item['url'];path=urlsplit(u).path
        if '/plan/' in path:key='plan-'+path.split('/plan/')[1].split('/')[0]
        elif 'im-cdn.it' in u and '/image/' in path:key='immo-'+path.split('/image/')[1].split('/')[0]
        else:key=re.sub(r'-\d{2,4}x\d{2,4}(?=\.)','',path.split('/')[-1])
        current=chosen.get(key)
        score=(100 if '/plan/' in u or u.lower().endswith('.pdf') else 0)+(10 if not re.search(r'-\d+x\d+\.',u) else 0)+(4 if '/xxl' in u or '/orig' in u else 0)
        item['priority']=score
        if current is None or score>current['priority']:chosen[key]=item
    return sorted(chosen.values(),key=lambda i:-i['priority'])

def process(prop,out):
    pid=prop['id'];folder=out/pid;folder.mkdir(parents=True,exist_ok=True)
    result={'id':pid,'title':prop['title'],'startedAt':datetime.now(timezone.utc).isoformat(),'pages':[],'media':[],'limitations':['Media are candidates only; visual identity, plan tracing and QA must be reviewed before modeling.']}
    seen=set()
    for page_url in prop.get('sourceUrls',[]):
        if '/geo/' in page_url or ('idealista.it/vendita-case/' in page_url):continue
        page={'url':page_url,'readAt':datetime.now(timezone.utc).isoformat()}
        try:
            data,kind=download(page_url);text=data.decode('utf-8','replace')
            parser=SourceHTML(page_url);parser.feed(text)
            title=' '.join(parser.title_parts).strip()
            if re.search(r'access denied|just a moment|captcha|security verification',title,re.I):
                raise ValueError('Access challenge encountered; not bypassed')
            page.update({'title':title,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'readable':True})
            # Store only readable text and discovered media, never scripts, cookies, or headers.
            plain='\n'.join(parser.text)
            plain=re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','[public contact omitted]',plain)
            page['text']=plain[:32000]
            media=collect_urls(text,parser);page['candidateMediaCount']=len(media)
            for item in media[:45]:
                if len(result['media'])>=36:break
                try:
                    binary,mime=download(item['url'],18*1024*1024)
                    if mime not in ('image/jpeg','image/png','image/webp','application/pdf'):continue
                    sha=hashlib.sha256(binary).hexdigest()
                    if sha in seen:continue
                    seen.add(sha)
                    ext={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp','application/pdf':'.pdf'}[mime]
                    filename=f'{len(result["media"]):02d}-{sha[:12]}{ext}'
                    (folder/filename).write_bytes(binary)
                    item.update({'file':filename,'sha256':sha,'mimeType':mime,'pageUrl':page_url,'downloadedAt':datetime.now(timezone.utc).isoformat()})
                    result['media'].append(item)
                except Exception as exc:
                    item['downloadError']=str(exc)[:150]
            if result['media']:break
        except Exception as exc:page['error']=str(exc)[:200]
        finally:result['pages'].append(page)
    result['finishedAt']=datetime.now(timezone.utc).isoformat()
    (folder/'evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'id':pid,'readablePages':sum(p.get('readable',False) for p in result['pages']),'media':len(result['media']),'errors':[p.get('error') for p in result['pages'] if p.get('error')]}),flush=True)
    return {'id':pid,'title':prop['title'],'readablePages':sum(p.get('readable',False) for p in result['pages']),'mediaCount':len(result['media'])}

def main():
    args=argparse.ArgumentParser();args.add_argument('--out',required=True);o=args.parse_args();out=Path(o.out);out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    cat=json.loads((root/'out/data/catalog.json').read_text())
    props=[p for p in cat['properties'] if p['availability']['status']=='published' and p.get('model',{}).get('status')!='ready']
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda p:process(p,out),props))
    (out/'inventory.json').write_text(json.dumps({'checkedAt':datetime.now(timezone.utc).isoformat(),'properties':results,'newModelsCreated':0,'downloadedBytes':total_bytes},indent=2)+'\n')

if __name__=='__main__':main()
