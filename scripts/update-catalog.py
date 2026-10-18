#!/usr/bin/env python3
"""Build the public catalog atomically from private source checks and reviewed models."""
import argparse, copy, hashlib, json, os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

def read(path,default):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return default
def catalog(seed,work,old,dist=None):
    before={p['id']:p for p in old.get('properties',[])};properties=[]
    for p in seed['properties']:
        item={k:copy.deepcopy(p.get(k)) for k in ('id','title','locality','address','sourceUrls','historicalPrices')}
        facts=copy.deepcopy(p['chatFacts']);source=read(work/'sources'/(p['id']+'.json'),{})
        historical=before.get(p['id'],{}).get('historicalPrices',[])
        public_price=lambda price:{k:copy.deepcopy(price[k]) for k in ('priceEur','date','source') if k in price}
        item['historicalPrices']=[public_price(price) for price in historical]
        for price in p.get('historicalPrices',[]):
            price=public_price(price)
            if price not in item['historicalPrices']:item['historicalPrices'].append(price)
        source_fields=source.get('fields',{}) if source.get('readerAccessible') else {}
        for key in ('bedrooms','bathrooms','floors','condition','energy','parking'):
            if facts.get(key) is None and source_fields.get(key) is not None:facts[key]=source_fields[key]
        if source_fields.get('heating') and source_fields['heating'] not in facts.get('highlights',[]):facts.setdefault('highlights',[]).append('Riscaldamento dichiarato: '+source_fields['heating'])
        # Older indexed pages must not roll back later prices supplied by the source chat.
        if source_fields.get('priceEur') and source_fields['priceEur']!=facts.get('priceEur'):
            facts.setdefault('limitations',[]).append('Prezzo discordante nella lettura indicizzata: €'+format(source_fields['priceEur'],',').replace(',','.')+'. Conservato l’ultimo prezzo della chat in attesa di conferma diretta.')
        check=read(work/'source-checks'/(p['id']+'.json'),{})
        availability={'status':check.get('conclusion','unverified'),'checkedAt':check.get('checkedAt'),'reason':check.get('reason','Disponibilità online ancora da verificare.')}
        if p.get('userUnavailable') and availability['status']!='available':availability['status']='unavailable';availability['reason']='Non più disponibile secondo la segnalazione dell’utente del '+p['userUnavailable']['date']+'. Gli accessi bloccati non costituiscono una nuova conferma.'
        live=read(work/'live-facts'/(p['id']+'.json'),{})
        reader=read(work/'reader-facts'/(p['id']+'.json'),{})
        observed_method='direct_http'
        if reader and (not live or reader.get('checkedAt','')>live.get('checkedAt','')):
            if live:facts.update(live.get('facts',{}))
            live=reader;observed_method='public_reader'
        # Last observed facts survive a failed recheck and confirmed archiving.
        if live:
            facts.update(live.get('facts',{}));item['locality']=live.get('locality',item['locality'])
            item['sourceUrls']=list(dict.fromkeys(item['sourceUrls']+live.get('sourceUrls',[])))
            current=facts.get('priceEur');previous_price=before.get(p['id'],{}).get('facts',p['chatFacts']).get('priceEur')
            if current is not None and current!=previous_price:
                record={'priceEur':current,'date':(live.get('checkedAt') or check.get('checkedAt') or '')[:10],'source':next(iter(live.get('sourceUrls',[])), 'direct_http')}
                if record not in item['historicalPrices']:item['historicalPrices'].append(record)
        report=read(work/'models'/(p['id']+'-review.json'),{})
        eligibility=read(work/'evidence'/p['id']/'eligibility.json',{})
        qa=report.get('qa',{});independent=report.get('independentReview',{})
        artifact=None
        if dist and report.get('path') and report.get('path','').startswith('modelli/'):
            path=dist/report['path']
            if path.is_file():artifact=hashlib.sha256(path.read_bytes()).hexdigest()
        reviewed=bool(artifact) and report.get('status')=='ready' and all(qa.get(k) is True for k in ('staticPassed','browserPassed','geometryPassed','orthographicPassed')) and report.get('fidelity',{}).get('passed') is True and independent.get('passed') is True and independent.get('artifactSha256')==report.get('artifactSha256')==artifact
        if reviewed:
            model={k:report.get(k) for k in ('status','path','views','notes')};model['verifiedAt']=report.get('verifiedAt',report.get('qa',{}).get('verifiedAt'))
            model['artifactSha256']=artifact
            model['sourcePlans']=[{k:p.get(k) for k in ('url','label')} for p in report.get('sourcePlans',[]) if isinstance(p,dict) and isinstance(p.get('url'),str)]
            missing=report.get('unrenderedVolumes',[])
            model['unrenderedVolumes']=[v for v in missing if isinstance(v,str) and v.strip()]
            model['coverage']=report.get('coverage') or ('partial' if model['unrenderedVolumes'] else 'complete')
            preview='assets/'+p['id']+'.jpg'
            if (dist/preview).is_file():model['preview']=preview
        elif eligibility.get('status') in ('complete_plans','partial_plans','incomplete_current_state','structural_conflict'):
            model={'status':'in_review','path':None,'views':[],'notes':report.get('notes') or eligibility.get('notes') or ['Ricostruzione delle parti documentate in corso. I volumi non ricostruibili saranno elencati nella scheda del modello parziale.']}
        else:
            model={'status':'awaiting_plans','path':None,'views':[],'notes':['Ricostruzione da preparare: le parti documentate potranno essere pubblicate anche con volumi mancanti, esplicitamente elencati. Senza piante utilizzabili, fotografie sufficienti consentono una ricostruzione dei soli esterni.']+(eligibility.get('notes') or ['Fotografie e planimetrie della casa da acquisire o validare.'])}
        if availability['status']=='unavailable' and not reviewed:model={'status':'not_required','path':None,'views':[],'notes':['Scheda storica conservata; nessun nuovo modello viene costruito per un immobile non più disponibile.']}
        item.update(facts=facts,availability=availability,model=model)
        live_applied=bool(live)
        item['evidence']={'listingReadAt':live.get('checkedAt') if live_applied else source.get('readAt'),'sourceUpdatedAt':live.get('sourceUpdatedAt') if live_applied else source_fields.get('sourceUpdatedAt'),'method':observed_method if live_applied else ('public_reader_and_chat' if source.get('readerAccessible') else 'chat'),'note':live.get('evidenceNote','Annuncio identificativo letto sul sito pubblico dell’agenzia; i dati non confermati sono indicati nella scheda.') if live_applied else source.get('evidenceLimit','Dati della ricerca precedente; accesso alla fonte non completo.')}
        properties.append(item)
    return properties

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seed',required=True);p.add_argument('--work',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    seed=read(Path(a.seed),{});out=Path(a.out);old=read(out,{});props=catalog(seed,Path(a.work),old,out.parent.parent)
    old_props=old.get('properties',[]);changed=props!=old_props
    result={'schemaVersion':1,'updatedAt':datetime.now(ZoneInfo('Europe/Rome')).isoformat() if changed else old.get('updatedAt'),'properties':props}
    out.parent.mkdir(parents=True,exist_ok=True);temp=out.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');os.replace(temp,out)
    digest=hashlib.sha256(out.read_bytes()).hexdigest();counts={s:sum(x['availability']['status']==s for x in props) for s in ('available','unavailable','unverified')}
    print(json.dumps({'count':len(props),'changed':changed,'availability':counts,'models':sum(x['model']['status']=='ready' for x in props),'sha256':digest}))
