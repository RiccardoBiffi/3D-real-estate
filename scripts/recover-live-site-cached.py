#!/usr/bin/env python3
"""Recover live manifest/catalog; reuse only byte-identical, hash-verified assets.

This avoids fetching unchanged assets through interactive HTML routes. It never
follows login redirects or substitutes stale catalog data for a fresh response.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('recovery', root / 'scripts/recover-live-site.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
original_capture = r.capture
provenance = {'fetchedDirectly': [], 'reusedMatchingManifestHash': []}

class ReportRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        # Do not print query strings, cookies, tokens, or response bodies.
        raise ValueError('Public asset redirects to ' + target.scheme + '://' + target.netloc + target.path + '; authentication was not bypassed')

def direct(name):
    if name != 'source-integrity.json' and not r.path_ok(name):
        raise ValueError('Unsafe asset path')
    print('Reading public asset: ' + name, flush=True)
    request = Request(r.ORIGIN + '/' + name, headers={'User-Agent': 'Case-in-3D-owner-recovery/1.1', 'Cache-Control': 'no-cache'})
    with build_opener(ReportRedirect()).open(request, timeout=35) as response:
        if response.status != 200:
            raise ValueError('Non-200 response for ' + name)
        data = response.read(r.MAX_FILE + 1)
    if not data or len(data) > r.MAX_FILE:
        raise ValueError('Invalid public asset size')
    provenance['fetchedDirectly'].append(name)
    return data

def cached_capture(destination, getter=direct):
    expected = {}
    def verified(name):
        if name == 'source-integrity.json':
            data = getter(name)
            if not expected:
                expected.update(json.loads(data).get('files', {}))
            return data
        if name != 'data/catalog.json' and r.path_ok(name):
            for folder in ('out', 'dist'):
                candidate = root / folder / name
                if candidate.is_file() and not candidate.is_symlink():
                    data = candidate.read_bytes()
                    if r.digest(data) == expected.get(name):
                        provenance['reusedMatchingManifestHash'].append(name)
                        return data
        return getter(name)
    return original_capture(destination, verified)

if __name__ == '__main__':
    r.capture = cached_capture
    r.main()
    path = root / 'maintenance/live-recovery.json'
    report = json.loads(path.read_text())
    report['retrievalProvenance'] = provenance
    report['source'] = 'fresh-direct-public-manifest-and-catalog; unchanged assets verified by SHA-256'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'directReads': len(provenance['fetchedDirectly']), 'unchangedAssetsVerified': len(provenance['reusedMatchingManifestHash'])}))
