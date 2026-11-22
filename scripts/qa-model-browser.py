#!/usr/bin/env python3
"""Offline file:// interaction QA, not architectural fidelity approval."""
import argparse, hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

def run(path,out,views):
    out.mkdir(parents=True,exist_ok=True)
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'htmlSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':'Chromium desktop/mobile emulation, offline file://; visual/source comparison is a separate approval','devices':[],'errors':[]}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CASE_3D_CHROMIUM') or None,args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage'])
        report['browserVersion']=browser.version
        for mobile in (False,True):
            name='mobile' if mobile else 'desktop';width,height=(430,800) if mobile else (960,640)
            ctx=browser.new_context(viewport={'width':width,'height':height},offline=True,has_touch=mobile,is_mobile=mobile,device_scale_factor=1,reduced_motion='reduce',service_workers='block')
            page=ctx.new_page();errors=[];requests=[];checks={}
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
            ctx.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:','ws:','wss:')) else None)
            device={'name':name,'viewport':[width,height],'checks':checks,'screenshots':[],'consoleErrors':errors,'networkRequests':requests};report['devices'].append(device)
            try:
                page.goto(path.as_uri(),wait_until='load',timeout=30000)
                page.wait_for_function('window.__sceneState?.ready && window.__sceneState.frames>1',timeout=20000)
                state=lambda:page.evaluate('window.__sceneState')
                def settle():
                    f=state()['frames'];page.wait_for_function('n=>window.__sceneState.frames>n+2',arg=f,timeout=15000)
                checks['offlineLocalFile']=page.url==path.as_uri()
                checks['viewCount']=state()['viewCount']==views
                checks['visibleCanvas']=page.locator('canvas').evaluate('c=>c.width>64&&c.height>64&&getComputedStyle(c).display!=="none"')
                checks['noVisibleBodyText']=not page.locator('body').inner_text().strip()
                for i in range(views):
                    page.keyboard.press(str(i+1) if i<9 else 'r');settle()
                    checks[f'view_{i}']=state()['mode']==i
                    shot=f'{name}-view-{i}.png';page.screenshot(path=str(out/shot));device['screenshots'].append(shot)
                    page.keyboard.press('t');settle()
                    checks[f'orthographic_{i}']=state().get('orthographic') is True
                    page.screenshot(path=str(out/f'{name}-top-{i}.png'))
                page.keyboard.press('r');settle();checks['viewCycle']=state()['mode']==0
                if not mobile:
                    before=state()['camera'];page.mouse.move(width*.5,height*.5);page.mouse.down();page.mouse.move(width*.7,height*.6,steps=6);page.mouse.up();settle();checks['mouseOrbit']=abs(state()['camera']['yaw']-before['yaw'])>.01
                    before=state()['camera'];page.mouse.wheel(0,-220);settle();checks['wheelZoom']=abs(state()['camera']['distance']-before['distance'])>.1
                    before=state()['camera'];page.mouse.down(button='right');page.mouse.move(width*.5,height*.5,steps=6);page.mouse.up(button='right');settle();checks['mousePan']=state()['camera']['target']!=before['target']
                    page.mouse.dblclick(width*.5,height*.5);settle();checks['doubleClick']=state()['mode']==1%views
                else:
                    session=ctx.new_cdp_session(page)
                    def touch(kind,pts):session.send('Input.dispatchTouchEvent',{'type':kind,'touchPoints':[{'x':x,'y':y,'id':i,'radiusX':2,'radiusY':2} for i,(x,y) in enumerate(pts)]})
                    before=state()['camera'];touch('touchStart',[(150,330)])
                    for j in range(1,6):touch('touchMove',[(150+j*17,330+j*5)])
                    touch('touchEnd',[]);settle();checks['touchOrbit']=abs(state()['camera']['yaw']-before['yaw'])>.01
                    before=state()['camera'];touch('touchStart',[(160,400),(260,400)])
                    for j in range(1,6):touch('touchMove',[(160-j*7,400),(260+j*7,400)])
                    touch('touchEnd',[]);settle();checks['pinchZoom']=abs(state()['camera']['distance']-before['distance'])>.1
                    before=state()['camera'];touch('touchStart',[(140,390),(260,390)])
                    for j in range(1,6):touch('touchMove',[(140+j*6,390+j*5),(260+j*6,390+j*5)])
                    touch('touchEnd',[]);settle();checks['twoFingerPan']=state()['camera']['target']!=before['target']
                    # Software WebGL may delay separate automation round trips.
                    # Preserve the actual input interval with trusted CDP events.
                    page.wait_for_timeout(400)
                    page.evaluate("window.__qaTouchLog=[];for(const type of ['pointerdown','pointerup'])document.querySelector('canvas').addEventListener(type,e=>window.__qaTouchLog.push({type:e.type,timeStamp:e.timeStamp,trusted:e.isTrusted,pointerType:e.pointerType}))")
                    tap_base=time.time()
                    for offset in (0,.18):
                        session.send('Input.dispatchTouchEvent',{'type':'touchStart','timestamp':tap_base+offset,'touchPoints':[{'x':215,'y':400,'id':0,'radiusX':2,'radiusY':2}]})
                        session.send('Input.dispatchTouchEvent',{'type':'touchEnd','timestamp':tap_base+offset+.03,'touchPoints':[]})
                    settle();page.wait_for_timeout(400);settle()
                    events=page.evaluate('window.__qaTouchLog');device['doubleTapEvents']=events
                    ups=[e for e in events if e['type']=='pointerup' and e['pointerType']=='touch']
                    checks['doubleTapInput']=len(ups)==2 and all(e['trusted'] for e in ups) and 100<ups[1]['timeStamp']-ups[0]['timeStamp']<300
                    checks['doubleTap']=state()['mode']==1%views
                page.keyboard.press('Home');settle();checks['reset']=state()['mode']==0
                checks['noExternalNetwork']=not requests;checks['noConsoleErrors']=not errors
                device['finalState']=state()
                for k,v in checks.items():
                    if not v:report['errors'].append(name+': '+k)
            except Exception as e:
                report['errors'].append(name+': '+str(e)[:500])
                try:page.screenshot(path=str(out/(name+'-failure.png')))
                except Exception:pass
            finally:ctx.close()
        browser.close()
    report['passed']=not report['errors'];(out/'qa-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'id':path.stem,'passed':report['passed'],'errors':report['errors'],'sha256':report['htmlSha256']}));return report['passed']

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('html',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--views',type=int,required=True);a=ap.parse_args();raise SystemExit(0 if run(a.html.resolve(),a.out,a.views) else 1)
