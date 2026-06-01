"""Simple connectivity/check script for France Travail endpoints.
Usage: python3 scripts/check_ft_proxy.py
It prints relevant proxy env vars and attempts a token request using values from config.py.
"""
import os
import requests
from importlib import import_module

print('ENV PROXY vars:')
for k in ('HTTP_PROXY','http_proxy','HTTPS_PROXY','https_proxy','NO_PROXY','no_proxy'):
    print(f'  {k}={os.environ.get(k)!r}')

try:
    cfg = import_module('config')
    cid = getattr(cfg, 'FT_CLIENT_ID', None)
    csec = getattr(cfg, 'FT_CLIENT_SECRET', None)
    print('\nLoaded config FT_CLIENT_ID present:', bool(cid))
except Exception as e:
    print('\nCould not import config:', e)
    cid = csec = None

if not cid or not csec:
    print('\nNo credentials available — skipping token request test.')
    raise SystemExit(0)

from tools.france_travail import FT_TOKEN_URL
print('\nTesting token endpoint:', FT_TOKEN_URL)
try:
    r = requests.post(FT_TOKEN_URL, data={
        'grant_type': 'client_credentials',
        'client_id': cid,
        'client_secret': csec,
    }, timeout=10)
    print('Status:', r.status_code)
    print('Headers sample:', dict(r.headers) if r.headers else {})
    txt = r.text
    print('Body length:', len(txt))
    try:
        print('JSON keys:', list(r.json().keys()))
    except Exception as e:
        print('JSON parse failed:', e)
except Exception as e:
    print('Request failed:', type(e), e)
    raise
