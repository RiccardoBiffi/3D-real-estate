#!/usr/bin/env python3
"""Controlli strutturali e browser offline con screenshot di ogni vista."""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external = []
        self.canvas = 0

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'canvas':
            self.canvas += 1
        for key in ('src', 'href', 'poster'):
            value = attr.get(key) or ''
            if tag in ('script','link','img','iframe','video','audio','source') and value and not value.startswith(('data:', '#')):
                self.external.append(value)

def static(path):
    source = path.read_text()
    parser = Resources()
    parser.feed(source)
    return {'canvas': bool(parser.canvas), 'selfContained': not parser.external,
            'startTime': 'name="creation-started"' in source,
            'finishTime': 'name="creation-finished"' in source,
            'renderingCode': 'webgl' in source.lower()}

def check_device(browser, path, output, views, mobile=False, gestures=True):
    from PIL import Image, ImageStat
    name = 'mobile' if mobile else 'desktop'
    size = (340,480) if mobile else (564,388)
    context = browser.new_context(viewport=dict(zip(('width','height'),size)), has_touch=mobile,
                                  is_mobile=mobile, device_scale_factor=1, offline=True,
                                  reduced_motion='reduce', service_workers='block')
    page = context.new_page()
    errors, requests, checks = [], [], {}
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
    page.on('request',lambda r: requests.append(r.url) if r.url.startswith(('https:','http:','ws:','wss:')) else None)
    def state(): return page.evaluate('window.__sceneState')
    def settle():
        frame = state()['frames']
        page.wait_for_function('n=>window.__sceneState.frames>n+1',arg=frame,timeout=16000)
    try:
        # set_content loads exactly the final file bytes even when a managed browser forbids file://.
        page.set_content(path.read_text(),wait_until='load',timeout=30000)
        page.wait_for_function('window.__sceneState?.ready && window.__sceneState.frames>1',timeout=25000)
        checks['viewCount'] = state().get('viewCount')==views
        checks['noVisibleText'] = not page.locator('body').inner_text().strip()
        for i in range(views):
            page.keyboard.press(str(i+1) if i<9 else 'r')
            settle()
            checks['view'+str(i)] = state()['mode']==i
            shot = page.screenshot(type='jpeg',quality=76,timeout=20000)
            (output/f'{name}-{i:02d}.jpg').write_bytes(shot)
            rgb=Image.open(io.BytesIO(shot)).convert('RGB')
            checks['pixels'+str(i)] = max(ImageStat.Stat(rgb).stddev)>3.5
            if not mobile:
                page.keyboard.press('t')
                settle()
                topstate=state()
                if 'orthographic' in topstate:
                    checks['top'+str(i)] = bool(topstate['orthographic'])
                (output/f'alto-{i:02d}.jpg').write_bytes(page.screenshot(type='jpeg',quality=74))
        page.keyboard.press('r')
        settle()
        checks['cycle'] = state()['mode']==0
        if gestures:
            if mobile:
                client=context.new_cdp_session(page)
                def touch(kind, points):
                    client.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'x':x,'y':y,'id':j} for j,(x,y) in enumerate(points)]})
                before=state()['camera']
                touch('touchStart',[(100,210)])
                for j in range(1,6):touch('touchMove',[(100+j*12,210+j*4)])
                touch('touchEnd',[]);settle()
                checks['touchOrbit'] = before!=state()['camera']
                before=state()['camera']
                touch('touchStart',[(100,225),(220,225)])
                for j in range(1,6):touch('touchMove',[(100-j*5,225),(220+j*5,225)])
                touch('touchEnd',[]);settle()
                checks['pinch'] = abs(before['distance']-state()['camera']['distance'])>.015
                page.wait_for_timeout(450)
                ts=time.time()
                for kind,delta,points in [('touchStart',0,[(160,220)]),('touchEnd',.055,[]),('touchStart',.13,[(160,220)]),('touchEnd',.18,[])]:
                    client.send('Input.dispatchTouchEvent',{'type':kind,'timestamp':ts+delta,'touchPoints':[{'x':x,'y':y,'id':0} for x,y in points]})
                settle()
                checks['doubleTap'] = state()['mode']==1
            else:
                before=state()['camera'];page.mouse.move(180,160);page.mouse.down();page.mouse.move(260,180,steps=5);page.mouse.up();settle()
                checks['orbit'] = before!=state()['camera']
                before=state()['camera'];page.mouse.wheel(0,-160);settle()
                checks['zoom'] = abs(before['distance']-state()['camera']['distance'])>.015
                before=state()['camera'];page.mouse.down(button='right');page.mouse.move(210,200,steps=5);page.mouse.up(button='right');settle()
                checks['pan'] = before['target']!=state()['camera']['target'] if 'target' in before else before!=state()['camera']
                page.mouse.dblclick(242,180);settle()
                checks['doubleClick'] = state()['mode']==1
        page.keyboard.press('Home');settle()
        checks['reset'] = state()['mode']==0
    except Exception as exc:
        errors.append(str(exc)[:650])
    finally:
        context.close()
    return {'device':name,'checks':checks,'errors':errors,'requests':requests,
            'passed':bool(checks) and all(checks.values()) and not errors and not requests}

def launch(pw):
    executable=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser')
    return pw.chromium.launch(headless=True,executable_path=executable,args=['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage'])

def browse(path,out,views,browser):
    out.mkdir(parents=True,exist_ok=True)
    devices=[check_device(browser,path,out,views,mobile) for mobile in (False,True)]
    report={'id':path.stem,'checkedAt':datetime.now(timezone.utc).isoformat(),'engine':'Chromium '+browser.version,
            'method':'Contenuto del singolo HTML caricato offline in Chromium. Desktop e dispositivo touch emulato.',
            'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'static':static(path),'devices':devices}
    report['passed']=all(report['static'].values()) and all(d['passed'] for d in devices)
    (out/'qa.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('html',type=Path);p.add_argument('--browser',action='store_true');p.add_argument('--views',type=int)
    p.add_argument('--out',type=Path,default=Path('/tmp/qa-scena'))
    a=p.parse_args()
    if a.browser:
        if not a.views:p.error('--views indica il numero reale di viste')
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=launch(pw);report=browse(a.html,a.out,a.views,browser);browser.close()
            print(json.dumps({'passed':report['passed'],'report':str(a.out/'qa.json')}));raise SystemExit(not report['passed'])
    checks=static(a.html);print(json.dumps(checks));raise SystemExit(not all(checks.values()))
