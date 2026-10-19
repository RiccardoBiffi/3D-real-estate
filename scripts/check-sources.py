#!/usr/bin/env python3
"""Check exact, authorized public listing URLs. Publication requires a readable direct listing; other outcomes are archived."""
import argparse, concurrent.futures, html, json, re, subprocess, tempfile, time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

def now():return datetime.now(ZoneInfo('Europe/Rome')).isoformat()
def collection_url(url):
    path=urlparse(url).path
    if re.search(r'/(?:annunci/\d+|immobile/\d+|immobili/\d+)',path) or re.search(r'/\d+\.html$',path):return False
    return bool(re.search(r'^/(?:geo/|vendita-case(?:/|$)|vendita(?:/|$)|ricerca(?:/|$)|search(?:/|$))',path))
def check(url,transport='urllib'):
    record={'url':url,'method':'http_direct','checkedAt':now()}
    try:
        if transport=='curl':
            with tempfile.TemporaryDirectory(prefix='listing-check-') as tmp:
                path=Path(tmp)/'body.html'
                response=subprocess.run(['curl','--silent','--show-error','--location','--max-time','25','--max-filesize','8000000','-H','Cache-Control: no-cache','-o',str(path),'-w','%{http_code}\n%{url_effective}',url],capture_output=True,text=True)
                if response.returncode:return {**record,'status':None,'state':'blocked','reason':response.stderr.strip(),'transport':'curl'}
                code,final=response.stdout.split('\n',1);status=int(code);body=path.read_text(errors='replace')
                record['transport']='curl'
        else:
            with urlopen(Request(url),timeout=22) as response:
                body=response.read(8_000_000).decode('utf-8',errors='replace');status=response.status;final=response.url
    except HTTPError as error:
        status=error.code;body=error.read(100_000).decode('utf-8',errors='replace');final=error.url
    except (URLError,TimeoutError,OSError) as error:
        return {**record,'status':None,'state':'blocked','reason':type(error).__name__}
    record.update(status=status,finalUrl=final)
    # Contact forms can load reCAPTCHA/DataDome on fully readable listings.
    # Inspect rendered text rather than treating a script name as a denial.
    visible=re.sub(r'<(script|style)\b[^>]*>.*?</\1\s*>',' ',body,flags=re.I|re.S)
    visible=html.unescape(re.sub(r'<[^>]+>',' ',visible))
    visible=re.sub(r'\s+',' ',visible)
    challenge=bool(re.search(r'access denied|verify you are human|unusual traffic|enable javascript and cookies|please enable js and disable any ad blocker|complete the captcha',visible,re.I))
    removed=bool(re.search(r'(?:annuncio|immobile)[^.]{0,80}(?:non [èe] più disponibile|rimosso|scaduto)',visible,re.I))
    same_path=urlparse(url).path.rstrip('/')==urlparse(final).path.rstrip('/')
    price=re.search(r'(?:€|EUR|price|prezzo)\s*:?\s*\d[\d.,]*|\d[\d.,]*\s*(?:€|EUR)|\b\d{3}[.]\d{3}\b',visible,re.I)
    details=re.search(r'.{0,35}(?:camere|bagni|superficie|floorplan|planimetr|bedrooms|\bmq\b|locali).{0,65}',visible,re.I)
    plausible=bool(price and details)
    title=re.search(r'<(?:title|h1)\b[^>]*>(.*?)</(?:title|h1)>',body,re.I|re.S)
    record['title']=html.unescape(re.sub('<[^>]+>',' ',title.group(1))).strip() if title else None
    record['readableFields']={'title':record['title'],'price':price.group(0) if price else None,'details':details.group(0) if details else None}
    generic_title=bool(re.search(r'^Annunci case e appartamenti in vendita e in affitto',record['title'] or '',re.I))
    if status in (403,429,401) or status>=500 or challenge:record['state']='blocked'
    elif removed or status in (404,410):record['state']='removed'
    elif status==200 and same_path and plausible and record['title'] and not generic_title and not collection_url(url):record['state']='active'
    else:record['state']='uncertain'
    record['explicitRemovedMessage']=removed
    return record
def conclude(checks,user_unavailable=False,exact_search_complete=False,previous_unavailable=False):
    if any(c.get('state')=='active' for c in checks):return 'published','Pagina identificativa letta direttamente: titolo, prezzo e informazioni sull’immobile accessibili.'
    return 'archived','Nessuna fonte online fresca leggibile individuata nell’ultimo controllo. Questo stato non certifica la vendita o il ritiro dell’immobile.'

def run(prop,out_dir,transport='urllib'):
    out=out_dir/(prop['id']+'.json')
    previous=json.loads(out.read_text()) if out.exists() else {}
    checks=[]
    for url in prop['sourceUrls']:
        checks.append(check(url) if transport=='urllib' else check(url,transport));time.sleep(.2)
    conclusion,reason=conclude(checks,bool(prop.get('userUnavailable')),previous_unavailable=previous.get('conclusion')=='unavailable')
    last_confirmed=previous.get('lastConfirmedAvailability')
    if previous.get('conclusion') in ('published','archived') and not last_confirmed:last_confirmed={'status':previous['conclusion'],'checkedAt':previous.get('checkedAt')}
    if conclusion=='published':last_confirmed={'status':'published','checkedAt':now()}
    result={'id':prop['id'],'checkedAt':now(),'checks':checks,'conclusion':conclusion,'reason':reason}
    if last_confirmed:result['lastConfirmedAvailability']=last_confirmed
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int);p.add_argument('--out',required=True);p.add_argument('--transport',choices=['curl','urllib'],default='curl')
    a=p.parse_args();props=json.loads(Path(a.inventory).read_text())['properties'][a.start:a.end];out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        for result in executor.map(lambda prop:run(prop,out,a.transport),props):print(json.dumps({'id':result['id'],'conclusion':result['conclusion'],'statuses':[x.get('status') for x in result['checks']]}),flush=True)
