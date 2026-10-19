#!/usr/bin/env python3
"""Verify favorite persistence, archive/removal protection, and storage failures."""
import argparse, copy, json, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

p=argparse.ArgumentParser()
p.add_argument('--base',default='http://127.0.0.1:8874/')
p.add_argument('--catalog',default='out/data/catalog.json')
p.add_argument('--out',required=True)
a=p.parse_args(); catalog=json.loads(Path(a.catalog).read_text())
out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
results=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader'])
    for device,width in [('desktop',1280),('mobile',390)]:
        page=browser.new_page(viewport={'width':width,'height':844}); errors=[]
        # This suite exercises saved listings; scene geometry has its own QA.
        page.route('**/modelli/**',lambda route:route.fulfill(content_type='text/html',body='<!doctype html><title>Scene fixture</title>'))
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(a.base); page.wait_for_selector('.property-card')
        pid=page.locator('.catalog-card-shell>.favorite-toggle').first.get_attribute('data-favorite')
        button=f'.catalog-card-shell>[data-favorite="{pid}"]'
        page.locator(button).click()
        assert page.locator(button).get_attribute('aria-pressed')=='true'
        assert page.locator('#overview').is_visible() and page.locator('#favorites-count').inner_text()=='1'
        page.locator('#favorites-link').click(); page.wait_for_url('**/#preferiti')
        page.wait_for_function("document.querySelector('#page-title').textContent==='I tuoi preferiti'")
        assert page.locator('.property-card').count()==1
        assert page.locator('#availability-filter').input_value()=='all'
        page.reload(); page.wait_for_selector('.property-card')
        assert page.locator(button).get_attribute('aria-pressed')=='true'
        page.locator('.property-card').click(); page.wait_for_selector('#property-details',state='visible')
        detail=f'#property-details [data-favorite="{pid}"]'
        assert page.locator(detail).get_attribute('aria-pressed')=='true'
        page.locator(detail).click(); assert page.locator(detail).get_attribute('aria-pressed')=='false'
        page.locator(detail).click(); page.locator('#favorites-link').click()
        page.wait_for_function("document.querySelector('#page-title').textContent==='I tuoi preferiti'")
        archived=copy.deepcopy(catalog)
        next(p for p in archived['properties'] if p['id']==pid)['availability']['status']='archived'
        page.route('**/data/catalog.json',lambda route:route.fulfill(json=archived))
        page.reload(); page.wait_for_selector('.property-card')
        assert page.locator('.property-card').count()==1
        assert page.locator('.property-card .archived').inner_text()=='Archiviato'
        page.unroute('**/data/catalog.json')
        missing=copy.deepcopy(catalog); missing['properties']=[p for p in missing['properties'] if p['id']!=pid]
        page.route('**/data/catalog.json',lambda route:route.fulfill(json=missing))
        page.reload(); page.wait_for_selector('.property-card')
        assert page.locator('.property-card').count()==1
        assert page.locator('.property-card .archived').inner_text()=='Archiviato'
        page.locator('.property-card').click(); page.wait_for_selector('#property-details',state='visible')
        assert 'scheda salvata nei preferiti è conservata' in page.locator('#property-details').inner_text()
        page.locator('#favorites-link').click()
        page.wait_for_function("document.querySelector('#page-title').textContent==='I tuoi preferiti'")
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/f'favorites-{device}.png'),full_page=True)
        page.locator(button).click(); assert page.locator('.property-card').count()==0
        page.reload(); page.wait_for_selector('#catalog-empty',state='visible')
        assert page.locator('#favorites-count').inner_text()=='0'
        page.unroute('**/data/catalog.json')
        page.goto(a.base+'#panoramica'); page.wait_for_selector('.property-card')
        page.evaluate("() => { Storage.prototype.setItem=function(){throw new DOMException('Full','QuotaExceededError')}; }")
        page.locator('.catalog-card-shell>.favorite-toggle').first.click()
        assert page.locator('#favorites-count').inner_text()=='0'
        assert 'Salvataggio non riuscito' in page.locator('#toast').inner_text()
        assert not errors, errors
        results.append({'device':device,'passed':True,'checks':['home star','detail sync','favorites navigation','reload persistence','archived favorite retained','missing catalog entry retained','saved details accessible','explicit removal persists','storage failure reported','no horizontal overflow','no JS errors']})
        page.close()
    browser.close()
(out/'report.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'passed':True,'devices':len(results),'checks':sum(len(r['checks']) for r in results)}))
