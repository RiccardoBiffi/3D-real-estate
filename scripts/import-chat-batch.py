#!/usr/bin/env python3
"""Merge reviewed property facts from exact source-chat messages, without publishing them.

Input is private JSON: chatId, messages[{id,turnId,role,text,date,properties[]}].
Each property has evidenceQuote (an exact substring of that message), existingId
when identity was resolved manually, and normalized catalog fields. Facts are
extracted by the local agent; this script never performs an independent search.
"""
import argparse, copy, hashlib, json, os, re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

FACT_KEYS=('priceEur','areaHabitableM2','areaWalkableM2','areaCommercialM2','areaNotes','gardenM2','landM2','parking','floors','bedrooms','bathrooms','condition','energy','bus','highlights','limitations','description','works')
def canonical(url):
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or '.' not in p.hostname or p.username or p.password:raise ValueError('Unsafe or incomplete listing URL')
    host=p.hostname.lower().removeprefix('www.')
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
    return urlunsplit(('https',host,p.path.rstrip('/'),urlencode(query),''))

def merge(inventory,checkpoint,batch):
    if batch.get('chatId')!=inventory.get('chatId') or batch.get('chatId')!=checkpoint.get('chatId'):raise ValueError('Source chat identity mismatch')
    inv=copy.deepcopy(inventory);cp=copy.deepcopy(checkpoint)
    properties=inv['properties'];by_id={p['id']:p for p in properties};by_url={canonical(u):p['id'] for p in properties for u in p.get('sourceUrls',[])}
    messages={m['id']:m for m in cp.get('messages',[])};events=[]
    for msg in batch.get('messages',[]):
        if not msg.get('id') or not isinstance(msg.get('text'),str):raise ValueError('Missing exact message ID/text')
        digest=hashlib.sha256(msg['text'].encode('utf-8')).hexdigest()
        if messages.get(msg['id'],{}).get('contentSha256')==digest:continue
        for incoming in msg.get('properties',[]):
            candidate=copy.deepcopy(incoming);quote=candidate.pop('evidenceQuote',None)
            if not quote or quote not in msg['text']:raise ValueError('Property without exact source evidence quote')
            urls=list(dict.fromkeys(candidate.get('sourceUrls',[])))
            aliases={by_url[canonical(u)] for u in urls if canonical(u) in by_url}
            if len(aliases)>1:raise ValueError('Source URL aliases point to distinct existing houses; resolve identity first')
            existing=candidate.pop('existingId',None)
            if existing and existing not in by_id:raise ValueError('Unknown manually matched existingId')
            if existing and aliases and aliases!={existing}:raise ValueError('Manual identity conflicts with known source URL')
            pid=existing or (next(iter(aliases)) if aliases else candidate.get('id'))
            if not isinstance(pid,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',pid):raise ValueError('Missing stable property ID')
            if pid in by_id and not existing and not aliases:raise ValueError('Slug alone is not proof of the same property')
            new=pid not in by_id
            if new:
                if not candidate.get('title') or not candidate.get('address'):raise ValueError('New house requires exact identifying title/address')
                facts={k:([] if k in ('highlights','limitations') else None) for k in FACT_KEYS}
                prop={'id':pid,'title':candidate['title'],'locality':candidate.get('locality'),'address':candidate['address'],'sourceUrls':[],'chatFacts':facts,'historicalPrices':[],'status':'da_verificare','missingSourceUrl':not urls}
                properties.append(prop);by_id[pid]=prop
            else:prop=by_id[pid]
            previous=copy.deepcopy(prop)
            for key in ('title','locality','address'):
                if candidate.get(key) is not None:prop[key]=candidate[key]
            for url in urls:
                if not any(canonical(u)==canonical(url) for u in prop['sourceUrls']):prop['sourceUrls'].append(url)
                by_url[canonical(url)]=pid
            prop['missingSourceUrl']=not prop['sourceUrls']
            facts=candidate.get('chatFacts',{})
            for key,value in facts.items():
                if key not in FACT_KEYS:raise ValueError('Unknown fact field '+key)
                if value is not None:prop['chatFacts'][key]=copy.deepcopy(value)
            price=facts.get('priceEur')
            if price is not None and (new or price!=previous['chatFacts'].get('priceEur')):
                record={'priceEur':price,'date':msg.get('date'),'source':'chat','sourceMessageId':msg['id'],'sourceContentSha256':digest}
                if record not in prop['historicalPrices']:prop['historicalPrices'].append(record)
            if candidate.get('userUnavailable'):prop['userUnavailable']=candidate['userUnavailable'];prop['status']='non_disponibile'
            if new or prop!=previous:events.append({'id':pid,'change':'new' if new else 'updated','messageId':msg['id']})
        messages[msg['id']]={'id':msg['id'],'turnId':msg.get('turnId',msg['id']),'role':msg.get('role'),'contentSha256':digest,'characterCount':len(msg['text'])}
    cp['messages']=list(messages.values());cp['messageCount']=len(cp['messages']);cp['readAt']=datetime.now(ZoneInfo('Europe/Rome')).isoformat()
    if inv['properties']!=inventory['properties']:inv['generatedAt']=cp['readAt']
    return inv,cp,events

def atomic(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temporary,path)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--checkpoint',required=True);p.add_argument('--batch',required=True);a=p.parse_args()
    inv=json.loads(Path(a.inventory).read_text());cp=json.loads(Path(a.checkpoint).read_text());batch=json.loads(Path(a.batch).read_text());result,new_cp,events=merge(inv,cp,batch)
    # Hash/alias checks make reprocessing safe even if a crash occurs between these writes.
    atomic(a.inventory,result);atomic(a.checkpoint,new_cp);print(json.dumps({'events':events,'properties':len(result['properties']),'messages':new_cp['messageCount']},ensure_ascii=False))
