#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Model import Job
from tools.document_tools import generate_cover_letter_pdf_bytes
from flask_app import app
with app.app_context():
    job = Job.query.get(398)
    user_id = job.user_id
    import json
    user_cvs = Path('static') / 'uploads' / 'users' / str(user_id) / 'cvs'
    meta = {}
    if (user_cvs / 'cvs_meta.json').exists():
        meta = json.loads((user_cvs / 'cvs_meta.json').read_text(encoding='utf-8'))
    default = meta.get('_default')
    if default:
        candidate = user_cvs / default
        basics = json.loads(candidate.read_text(encoding='utf-8')).get('basics', {})
    else:
        basics = json.loads((Path('static') / 'cv.json').read_text(encoding='utf-8')).get('basics', {})
    addr = basics.get('address') or basics.get('location')
    city = basics.get('city')
    def _address_str_local(v):
        if not v:
            return ''
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            for k in ('address', 'formatted', 'streetAddress', 'street_address'):
                if k in v and v[k]:
                    return str(v[k])
            parts = [str(p) for p in (
                v.get('street'),
                v.get('postalCode') or v.get('postal_code') or v.get('postal'),
                v.get('city') or v.get('locality') or v.get('town'),
                v.get('region')
            ) if p]
            if parts:
                return ', '.join(parts)
            try:
                import json as _json
                return _json.dumps(v, ensure_ascii=False)
            except Exception:
                return str(v)
        try:
            return ' '.join(map(str, v))
        except Exception:
            return str(v)

    def norm(s):
        import re
        return re.sub(r'[^0-9a-zA-Z]+','', (s or '')).lower()
    print('raw addr:', addr)
    print('addr_str:', _address_str_local(addr))
    print('raw city:', city)
    print('norm addr:', norm(str(_address_str_local(addr))))
    print('norm city full:', norm(str(city)))
    import re
    city_only = re.sub(r'^\s*\d{5}\s*', '', str(city)).strip()
    print('city only:', city_only)
    print('norm city only:', norm(city_only))



