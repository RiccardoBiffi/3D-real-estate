#!/usr/bin/env python3
"""Extract listing facts/assets from a saved public reader result, keeping its evidence limits."""
import argparse, json, re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

def parse(raw, property_id, url):
    clean = re.sub(r'L\d+: ?', '', raw)
    lines = [x.strip() for x in clean.splitlines() if x.strip()]
    ref = re.search(r'cite(turn[^]+)', raw)
    refs = [(int(m.group(1)), m.group(2) or '', m.group(3)) for m in re.finditer(r'cite(\d+)†Image(?:: ([^†]*))?†([^]+)', raw)]
    plan_pos = re.search(r'\n(?:L\d+: )?Planimetria\s*\n', raw)
    plan_refs = []
    if plan_pos:
        part = raw[plan_pos.end():].split('Espandi', 1)[0].split('Scopri ogni angolo', 1)[0]
        plan_refs = [{'id':int(m.group(1)), 'label':m.group(2) or ''} for m in re.finditer(r'cite(\d+)†Image(?:: ([^†]*))?†([^]+)', part)]
    photo_refs = []
    before = raw.split('# ',1)[0]
    for m in re.finditer(r'cite(\d+)†Image(?:: ([^†]*))?†([^]+)', before):
        if 'pwm.im-cdn.it' in m.group(3):
            item={'id':int(m.group(1)), 'label':m.group(2) or ''}
            if item not in photo_refs: photo_refs.append(item)
    def after(key):
        try:
            idx=lines.index(key)
            value=lines[idx+1]
            return value if not value.startswith(('','[Button:')) else None
        except (ValueError,IndexError): return None
    fields={}
    for src,key in [('Camere da letto','bedrooms'),('Bagni','bathrooms'),('Piani edificio','floors')]:
        value=after(src)
        if value and re.fullmatch(r'\d+\+?',value): fields[key]=value if '+' in value else int(value)
    for src,key in [('Stato','condition'),('Riscaldamento','heating'),('Box, posti auto','parking'),('Tipologia','type')]:
        value=after(src)
        if value: fields[key]=value
    # Both price formats occur. Never treat the m² following a trailing euro sign as money.
    money=[]
    for pattern in [r'(?<![\d.])([\d]{1,3}(?:\.\d{3})+|\d{5,9})(?:,\d{2})?\s*€',r'€\s*([\d]{1,3}(?:\.\d{3})+|\d{5,9})(?![\d.])']:
        for m in re.finditer(pattern,clean):money.append((m.start(),int(m.group(1).replace('.',''))))
    if money:fields['priceEur']=min(money,key=lambda x:x[0])[1]
    for src,key in [(r'\*\s*(\d+) piani\b','floors'),(r'\*\s*(\d+) bagni\b','bathrooms')]:
        m=re.search(src,clean)
        if m and key not in fields:fields[key]=int(m.group(1))
    updated=re.search(r'Annuncio aggiornato il ([^\n]+)',clean)
    if updated:fields['sourceUpdatedAt']=updated.group(1).strip()
    energy=re.search(r'(?:Classe energetica:|Classe)\s*([A-G](?:[1-4+])?)\b',clean)
    if energy:fields['energy']=energy.group(1)
    sizes=re.search(r'(\d+) Foto\s+(\d+) Planimetr',clean)
    missing=bool(re.search(r'(?:non è più disponibile|annuncio (?:è stato )?(?:rimosso|scaduto)|immobile non (?:è )?più disponibile)', clean, re.I))
    failed=bool(re.search(r'Failed to fetch|Internal Error|Cache miss|403 Forbidden|Access Denied',raw,re.I))
    return {'id':property_id,'url':url,'readAt':datetime.now(ZoneInfo('Europe/Rome')).isoformat(),
        'method':'public_reader','referenceId':ref.group(1) if ref else None,
        'readerAccessible':not failed and len(clean)>600,'explicitRemovedMessage':missing,
        'availabilityVerifiedLive':False,'evidenceLimit':'Lettura pubblica/indicizzata; da sola non conferma la disponibilità attuale.',
        'fields':fields,'photoCountDeclared':int(sizes.group(1)) if sizes else None,
        'floorplanCountDeclared':int(sizes.group(2)) if sizes else None,
        'photoRefs':photo_refs,'floorplanRefs':plan_refs,'rawChars':len(raw)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--id',required=True);p.add_argument('--url',required=True);p.add_argument('--out',required=True)
    a=p.parse_args(); result=parse(Path(a.input).read_text(),a.id,a.url);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'id':a.id,'readerAccessible':result['readerAccessible'],'plans':len(result['floorplanRefs']),'photos':len(result['photoRefs']),'ref':result['referenceId']}))
