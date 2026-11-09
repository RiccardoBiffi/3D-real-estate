#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('recover-live-site.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

class RecoveryTests(unittest.TestCase):
    def fixture(self):
        prop = {'id': 'test-house', 'title': 'Test house', 'availability': {'status': 'published'},
                'priceHistory': [{'priceEur': 100000, 'date': '2026-01-01'}],
                'model': {'status': 'awaiting_plans', 'path': None}}
        catalog = {'properties': [prop]}
        assets = {'index.html': b'<!doctype html><html></html>', 'app.js': b'void 0;',
                  'styles.css': b'body{}', 'data/catalog.json': json.dumps(catalog).encode()}
        manifest = {'files': {n: r.digest(b) for n,b in assets.items()},
                    'catalogSha256': r.digest(assets['data/catalog.json'])}
        assets['source-integrity.json'] = json.dumps(manifest).encode()
        return assets, catalog

    def capture(self, assets):
        with tempfile.TemporaryDirectory() as d:
            return r.capture(Path(d), assets.__getitem__)

    def test_valid_capture(self):
        assets, catalog = self.fixture()
        self.assertEqual(self.capture(assets)[1], catalog)

    def test_corrupt_asset(self):
        assets, _ = self.fixture(); assets['app.js'] = b'changed'
        with self.assertRaises(ValueError): self.capture(assets)

    def test_path_traversal(self):
        assets, _ = self.fixture()
        m = json.loads(assets['source-integrity.json']); m['files']['../.github/evil.yml'] = r.digest(b'x')
        assets['source-integrity.json'] = json.dumps(m).encode()
        with self.assertRaises(ValueError): self.capture(assets)

    def test_no_card_deletion(self):
        _, old = self.fixture()
        with self.assertRaises(ValueError): r.guard_previous(old, {'properties': []})

    def test_no_price_history_loss(self):
        _, old = self.fixture(); new = json.loads(json.dumps(old)); new['properties'][0]['priceHistory'] = []
        with self.assertRaises(ValueError): r.guard_previous(old, new)

    def test_unchanged_inventory(self):
        _, old = self.fixture(); r.guard_previous(old, old)

    def test_no_unapproved_model(self):
        assets, catalog = self.fixture(); catalog['properties'][0]['model']['path'] = 'modelli/test-house.html'
        assets['data/catalog.json'] = json.dumps(catalog).encode()
        m = json.loads(assets['source-integrity.json']); m['files']['data/catalog.json'] = m['catalogSha256'] = r.digest(assets['data/catalog.json'])
        assets['source-integrity.json'] = json.dumps(m).encode()
        with self.assertRaises(ValueError): self.capture(assets)

    def test_changed_release(self):
        assets, _ = self.fixture(); calls = 0
        def getter(name):
            nonlocal calls
            if name == 'source-integrity.json':
                calls += 1
                if calls > 1: return b'{}'
            return assets[name]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): r.capture(Path(d), getter)

if __name__ == '__main__': unittest.main()
