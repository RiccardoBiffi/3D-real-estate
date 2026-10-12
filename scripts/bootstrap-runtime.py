#!/usr/bin/env python3
"""Restore reproducible, local QA/build dependencies; no data or credential changes."""
import argparse,importlib.metadata,json,os,shutil,subprocess,sys
from pathlib import Path

PYTHON_PACKAGES={'playwright':'1.63.0','pillow':'12.3.0','beautifulsoup4':'4.15.0','shapely':'2.2.0','pymupdf':'1.28.2'}
NODE_PACKAGES={'three':'0.186.1','esbuild':'0.28.2'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--python-target',default='/tmp/case-in-3d-python');p.add_argument('--node-target',required=True);a=p.parse_args()
    py=Path(a.python_target).resolve();node=Path(a.node_target).resolve();installed={}
    if py.is_dir():
        for package in importlib.metadata.distributions(path=[str(py)]):installed[package.metadata['Name'].lower()]=package.version
    missing=[f'{name}=={version}' for name,version in PYTHON_PACKAGES.items() if installed.get(name)!=version]
    if missing:subprocess.run([sys.executable,'-m','pip','install','--target',str(py),'--upgrade','--cache-dir','/tmp/case-in-3d-pip-cache',*missing],check=True)
    node_missing=[]
    for name,version in NODE_PACKAGES.items():
        try:actual=json.loads((node/'node_modules'/name/'package.json').read_text())['version']
        except (FileNotFoundError,json.JSONDecodeError,KeyError):actual=None
        if actual!=version:node_missing.append(name+'@'+version)
    if node_missing:subprocess.run(['npm','install','--prefix',str(node),'--cache','/tmp/case-in-3d-npm-cache',*node_missing],check=True)
    chrome=next((shutil.which(x) for x in ('google-chrome','chromium','chromium-browser') if shutil.which(x)),None)
    if not chrome:raise SystemExit('Chromium browser missing; preserve drafts and report the QA dependency failure.')
    print(json.dumps({'pythonPath':str(py),'nodeRuntime':str(node),'browser':chrome,'pythonPackages':PYTHON_PACKAGES,'nodePackages':NODE_PACKAGES}))
