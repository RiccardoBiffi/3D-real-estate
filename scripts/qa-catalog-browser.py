#!/usr/bin/env python3
"""Exercise the public catalog against its actual approved offline HTML scenes."""
import argparse,json,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8765/');p.add_argument('--catalog',required=True);p.add_argument('--out',required=True);p.add_argument('--ids',nargs='+',required=True);a=p.parse_args();catalog=json.loads(Path(a.catalog).read_text());properties={x['id']:x for x in catalog['properties']};out=Path(a.out);out.mkdir(parents=True,exist_ok=True);results=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader'])
 for device,w,h in [('desktop',1280,800),('mobile',390,844)]:
  page=browser.new_page(viewport={'width':w,'height':h});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));checks={};page.goto(a.base+'#panoramica');page.wait_for_function('document.querySelectorAll(".property-card").length>0')
  page.locator('#availability-filter').select_option('all');checks['full_catalog']=page.locator('.property-card').count()==len(properties)
  page.locator('#availability-filter').select_option('archived');checks['archive']=page.locator('.property-card').count()==sum(x['availability']['status']=='archived' for x in properties.values())
  page.locator('#availability-filter').select_option('all');page.locator('#model-filter').select_option('ready');checks['ready_filter']=page.locator('.property-card').count()==sum(x['model']['status']=='ready' for x in properties.values())
  for pid in a.ids:
   model=properties[pid]['model'];assert model['status']=='ready';page.evaluate('(id)=>location.hash=id',pid);page.wait_for_function("document.querySelector('iframe')?.contentWindow.__sceneState?.ready",timeout=60000)
   checks[pid+'_one_frame']=page.locator('iframe').count()==1;checks[pid+'_actual_views']=page.locator('#view-select option').count()==len(model['views'])
   if model['coverage']!='complete':
    text=page.locator('#model-coverage').inner_text();checks[pid+'_omissions_visible']=page.locator('#model-coverage').is_visible() and all(v in text for v in model['unrenderedVolumes'])
   mode=len(model['views'])-1
   if device=='desktop':page.locator(f'.view-tab[data-mode="{mode}"]').click()
   else:page.locator('#view-select').select_option(str(mode))
   page.wait_for_function('(m)=>document.querySelector("iframe").contentWindow.__sceneState.mode===m',arg=mode,timeout=30000);checks[pid+'_last_view']=True
   checks[pid+'_no_overflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(out/f'{pid}-{device}.png'),full_page=True)
  page.goto(a.base+'#trebiciano-130356648');page.wait_for_selector('#property-details',state='visible');checks['garden_range']= '250–300' in page.locator('#property-details').inner_text()
  page.route('**/data/catalog.json',lambda route:route.abort());page.reload();page.wait_for_selector('#catalog-error',state='visible');checks['fetch_error_visible']=page.locator('iframe').count()==0;page.unroute('**/data/catalog.json');page.locator('#retry-catalog').click();page.wait_for_function('document.querySelectorAll(".property-card").length>0');checks['retry_recovers']=True
  checks['no_javascript_errors']=not errors;results.append({'device':device,'checks':checks,'errors':errors});page.close()
 browser.close()
report={'passed':all(all(x['checks'].values()) for x in results),'scope':'Chromium desktop/mobile emulation; actual scenes and site controls, not physical-device proof','results':results};(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':report['passed'],'checks':sum(len(r['checks']) for r in results),'failures':[{k:v for k,v in r['checks'].items() if not v} for r in results]}));raise SystemExit(not report['passed'])
