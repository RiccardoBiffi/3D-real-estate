#!/usr/bin/env python3
"""Check exact, authorized public listing URLs. Blocks never imply an unavailable house."""
import argparse, concurrent.futures, json, re, time
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
def check(url):
    record={'url':url,'method':'http_direct','checkedAt':now()}
    try:
        with urlopen(Request(url),timeout=22) as response:
            body=response.read(8_000_000).decode('utf-8',errors='replace');status=response.status;final=response.url
    except HTTPError as error:
        status=error.code;body=error.read(100_000).decode('utf-8',errors='replace');final=error.url
    except (URLError,TimeoutError,OSError) as error:
        return {**record,'status':None,'state':'blocked','reason':type(error).__name__}
    record.update(status=status,finalUrl=final)
    challenge=bool(re.search(r'captcha|access denied|verify you are human|unusual traffic|enable javascript and cookies|datadome|px-captcha',body,re.I))
    removed=bool(re.search(r'(?:annuncio|immobile)[^<\n]{0,80}(?:non [èe] più disponibile|rimosso|scaduto)',body,re.I))
    same_path=urlparse(url).path.rstrip('/')==urlparse(final).path.rstrip('/')
    plausible=bool(re.search(r'(?:€|EUR|price)',body)) and bool(re.search(r'camere|bagni|superficie|floorplan|planimetr|bedrooms',body,re.I))
    if status in (403,429,401) or status>=500 or challenge:record['state']='blocked'
    elif removed or status in (404,410):record['state']='removed'
    elif status==200 and same_path and plausible and not collection_url(url):record['state']='active'
    else:record['state']='uncertain'
    record['explicitRemovedMessage']=removed
    return record
def conclude(checks,user_unavailable=False,exact_search_complete=False,previous_unavailable=False):
    if any(c.get('state')=='active' for c in checks):return 'available','Annuncio identificativo attivo letto con accesso HTTP pubblico diretto.'
    if user_unavailable:return 'unavailable','Non più disponibile secondo la segnalazione dell’utente del 29 settembre 2026; nessun annuncio attivo verificato direttamente.'
    if previous_unavailable:return 'unavailable','Archiviazione già confermata, conservata: nessun annuncio attivo dell’esatto immobile verificato nuovamente. Errori temporanei non riattivano la scheda.'
    if checks and all(c.get('state')=='removed' for c in checks) and exact_search_complete:return 'unavailable','Fonti identificative rimosse e ricerca delle copie pubbliche dell’esatto immobile conclusa senza annunci attivi.'
    if checks and all(c.get('state')=='removed' for c in checks):return 'unverified','Gli URL conosciuti risultano rimossi; resta da controllare se l’esatto immobile è stato ripubblicato da agenzie o altri portali.'
    return 'unverified','La disponibilità attuale non è confermata: fonti bloccate, incomplete o non accessibili. La lettura indicizzata non equivale a verifica live.'
def run(prop,out_dir):
    out=out_dir/(prop['id']+'.json')
    previous=json.loads(out.read_text()) if out.exists() else {}
    checks=[]
    for url in prop['sourceUrls']:
        checks.append(check(url));time.sleep(.2)
    conclusion,reason=conclude(checks,bool(prop.get('userUnavailable')),previous_unavailable=previous.get('conclusion')=='unavailable')
    last_confirmed=previous.get('lastConfirmedAvailability')
    if previous.get('conclusion') in ('available','unavailable') and not last_confirmed:last_confirmed={'status':previous['conclusion'],'checkedAt':previous.get('checkedAt')}
    if conclusion=='available':last_confirmed={'status':'available','checkedAt':now()}
    if conclusion=='unverified' and last_confirmed and last_confirmed.get('status')=='available' and last_confirmed.get('checkedAt'):reason+=' Ultima lettura diretta con annuncio attivo: '+last_confirmed['checkedAt'][:10]+'.'
    result={'id':prop['id'],'checkedAt':now(),'checks':checks,'conclusion':conclusion,'reason':reason}
    if last_confirmed:result['lastConfirmedAvailability']=last_confirmed
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int);p.add_argument('--out',required=True)
    a=p.parse_args();props=json.loads(Path(a.inventory).read_text())['properties'][a.start:a.end];out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        for result in executor.map(lambda prop:run(prop,out),props):print(json.dumps({'id':result['id'],'conclusion':result['conclusion'],'statuses':[x.get('status') for x in result['checks']]}),flush=True)
