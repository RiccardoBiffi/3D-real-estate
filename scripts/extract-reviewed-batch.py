#!/usr/bin/env python3
"""Fill missing draft sources from verified bundles, newest first."""
import hashlib
import json
import lzma
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
bundles = [
    ('batch-20261123.json.xz', '24eb63065fb7ab936d3dc6bd82d44f71da8b2f65c41736d1c12e677566e3ed19', 65),
    ('batch-20261109.json.xz', '36d97c59def1ebd5ea25f8fecf7a60a9792410923e950d36a4cc6d957f7731bf', 10),
]
catalog = json.loads((root / 'out/data/catalog.json').read_text())
known = {p['id']: p for p in catalog['properties']}
sources = root / 'models-source'
sources.mkdir(exist_ok=True)
expanded = 0
for name, digest, count in bundles:
    payload = (root / 'model-authoring' / name).read_bytes()
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError(f'{name}: authoring bundle integrity mismatch')
    decoder = lzma.LZMADecompressor(memlimit=256 * 1024 * 1024)
    items = json.loads(decoder.decompress(payload, max_length=4 * 1024 * 1024))
    if not decoder.eof or len(items) != count or len({item['id'] for item in items}) != count:
        raise ValueError(f'{name}: unexpected inventory')
    for item in items:
        pid = item['id']
        if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', pid) or pid not in known:
            raise ValueError(f'{name}: unknown property {pid}')
        prop = known[pid]
        dest = sources / (pid + '.json')
        if prop['availability']['status'] != 'published' or prop['model']['status'] == 'ready' or dest.exists():
            continue
        if not item.get('sources') or 'unrenderedVolumes' not in item:
            raise ValueError(f'{pid}: missing source or scope evidence')
        dest.write_text(json.dumps(item, ensure_ascii=False, indent=2) + '\n')
        expanded += 1
print(f'Expanded {expanded} missing draft sources.')
