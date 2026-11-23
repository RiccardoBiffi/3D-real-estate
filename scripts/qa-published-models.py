#!/usr/bin/env python3
"""Open every active, approved catalog HTML offline and verify its identity and renderer."""
import hashlib
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / 'out'
catalog = json.loads((out / 'data/catalog.json').read_text())
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=os.environ.get('CASE_3D_CHROMIUM'),
                                 args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    for prop in catalog['properties']:
        model = prop['model']
        if prop['availability']['status'] != 'published' or model['status'] != 'ready':
            continue
        path = out / model['path']
        print(f"Checking {prop['id']}", flush=True)
        if hashlib.sha256(path.read_bytes()).hexdigest() != model['artifactSha256']:
            raise ValueError(f'{path}: catalog digest mismatch')
        page = browser.new_page(offline=True, viewport={'width': 640, 'height': 480})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda req: errors.append(req.url) if req.url.startswith(('http:', 'https:')) else None)
        page.goto(path.as_uri())
        page.wait_for_function('window.__sceneState?.ready && window.__sceneState.frames > 1')
        if page.evaluate('window.__sceneState.viewCount') != len(model['views']):
            raise ValueError(f'{path}: unexpected view count')
        if errors:
            raise RuntimeError(f'{path}: {errors}')
        page.close()
    browser.close()
