#!/usr/bin/env python3
"""Recover the exact public Sites build. No deletions, invented data, or credentials."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, HTTPRedirectHandler, build_opener

ORIGIN = 'https://case-in-3d.biffi-riccardo91.chatgpt.site'
MAX_FILE = 24 * 1024 * 1024
MAX_TOTAL = 300 * 1024 * 1024

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused: public build may require authentication')

def path_ok(name):
    return isinstance(name, str) and bool(re.fullmatch(
        r'(?:index\.html|app\.js|styles\.css|data/[a-zA-Z0-9_-]+\.json|'
        r'modelli/[a-z0-9-]+\.html|assets/[a-zA-Z0-9_-]+\.(?:jpg|jpeg|png|webp|svg|js|css|woff2))', name))

def digest(data):
    return hashlib.sha256(data).hexdigest()

def fetch(name):
    if name != 'source-integrity.json' and not path_ok(name):
        raise ValueError('Unsafe asset path')
    req = Request(ORIGIN + '/' + name, headers={
        'User-Agent': 'Case-in-3D-owner-recovery/1.0', 'Cache-Control': 'no-cache'})
    with build_opener(NoRedirect()).open(req, timeout=35) as response:
        if response.status != 200:
            raise ValueError('Direct asset returned a non-200 status')
        data = response.read(MAX_FILE + 1)
    if not data or len(data) > MAX_FILE:
        raise ValueError('Asset is empty or exceeds the size limit')
    return data

def capture(destination, getter=fetch):
    raw = getter('source-integrity.json')
    manifest = json.loads(raw)
    files = manifest.get('files')
    if not isinstance(files, dict) or not 1 <= len(files) <= 600:
        raise ValueError('Missing or invalid public integrity manifest')
    required = {'index.html', 'app.js', 'styles.css', 'data/catalog.json'}
    if not required.issubset(files):
        raise ValueError('Public manifest omits required runtime files')
    total = 0
    for name, expected in files.items():
        if not path_ok(name) or not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
            raise ValueError('Unsafe path or malformed digest in public manifest')
        data = getter(name)
        total += len(data)
        if not data or len(data) > MAX_FILE or total > MAX_TOTAL or digest(data) != expected:
            raise ValueError('Downloaded asset fails integrity: ' + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    catalog_bytes = (destination / 'data/catalog.json').read_bytes()
    if digest(catalog_bytes) != manifest.get('catalogSha256'):
        raise ValueError('Catalog digest mismatch')
    catalog = json.loads(catalog_bytes)
    props = catalog.get('properties')
    if not isinstance(props, list) or not props:
        raise ValueError('Missing property inventory')
    ids = [p.get('id') for p in props]
    if any(not isinstance(i, str) or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', i) for i in ids):
        raise ValueError('Invalid property identities')
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate property identities')
    for prop in props:
        if prop.get('availability', {}).get('status') not in ('published', 'archived'):
            raise ValueError('Invalid publication state')
        model = prop.get('model', {})
        if model.get('status') == 'ready':
            name = model.get('path')
            if not isinstance(name, str) or not name.startswith('modelli/') or name not in files:
                raise ValueError('Approved model omitted by public manifest')
            if files[name] != model.get('artifactSha256'):
                raise ValueError('Approved-model digest disagrees with catalog')
            if model.get('preview') and model['preview'] not in files:
                raise ValueError('Model preview missing from manifest')
        elif model.get('path') is not None:
            raise ValueError('Unapproved model exposed by catalog')
    if getter('source-integrity.json') != raw or getter('data/catalog.json') != catalog_bytes:
        raise ValueError('Live release changed during capture; no import performed')
    (destination / 'source-integrity.json').write_bytes(raw)
    return manifest, catalog

def guard_previous(previous, current):
    old = {p['id']: p for p in previous['properties']}
    new = {p['id']: p for p in current['properties']}
    if old.keys() - new.keys():
        raise ValueError('Import would remove existing properties; favorites protection stops it')
    for pid, prop in old.items():
        for history_key in ('priceHistory', 'history'):
            history = prop.get(history_key)
            if isinstance(history, list):
                after = new[pid].get(history_key, [])
                if not isinstance(after, list) or any(item not in after for item in history):
                    raise ValueError('Import would discard recorded history: ' + pid)

def main():
    root = Path(__file__).resolve().parents[1]
    previous = json.loads((root / 'out/data/catalog.json').read_text())
    with tempfile.TemporaryDirectory(prefix='case-live-recovery-') as temporary:
        stage = Path(temporary)
        manifest, catalog = capture(stage)
        guard_previous(previous, catalog)
        validator_path = root / 'scripts/validate-catalog.py'
        spec = importlib.util.spec_from_file_location('validator', validator_path)
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        errors = validator.validate(catalog, stage)
        if errors:
            raise ValueError('Existing catalog validator rejected capture: ' + repr(errors))
        # Merge verified files only. Never remove old files, cards, or favorites assets.
        for folder in ('dist', 'out'):
            for source in stage.rglob('*'):
                if source.is_file():
                    target = root / folder / source.relative_to(stage)
                    if target.is_symlink():
                        raise ValueError('Refusing symlink target')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
        shutil.copyfile(stage / 'source-integrity.json', root / 'source-integrity.json')
    props = catalog['properties']
    pending = [p for p in props if p['availability']['status'] == 'published' and p.get('model', {}).get('status') != 'ready']
    receipt = {
        'checkedAt': datetime.now(timezone.utc).isoformat(), 'origin': ORIGIN,
        'source': 'fresh-direct-public-build', 'catalogSha256': manifest['catalogSha256'],
        'verifiedFiles': len(manifest['files']), 'properties': len(props),
        'published': sum(p['availability']['status'] == 'published' for p in props),
        'approvedModels': sum(p.get('model', {}).get('status') == 'ready' for p in props),
        'publishedWithoutModel': len(pending), 'deletedProperties': 0, 'deletedAssets': 0,
        'newModelsCreated': 0, 'sitesDeployed': False,
        'limitations': ['Public build recovered, not private Sites source or its Git history.',
                         'No new architectural or browser QA claimed for existing models.',
                         'Favorites remain browser-local; automatic deletion remains disabled.']}
    maintenance = root / 'maintenance'
    maintenance.mkdir(exist_ok=True)
    (maintenance / 'live-recovery.json').write_text(json.dumps(receipt, indent=2) + '\n')
    backlog = [{'id': p['id'], 'title': p['title'], 'sourceUrls': p.get('sourceUrls', []),
                'modelStatus': p.get('model', {}).get('status')} for p in pending]
    (maintenance / 'model-backlog.json').write_text(json.dumps(backlog, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
