#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask_app import app
from Model import Job
import json
from tools.cv_tools import generate_tailored_cv_pdf_bytes, build_cv_pdf_filename
from io import BytesIO


def resolve_user_cv(job):
    user_id = job.user_id
    user_cvs = Path('static') / 'uploads' / 'users' / str(user_id) / 'cvs'
    if user_cvs.exists():
        meta_path = user_cvs / 'cvs_meta.json'
        default = None
        try:
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
                default = meta.get('_default')
        except Exception:
            default = None
        if default:
            target = user_cvs / default
            if target.exists() and target.suffix.lower() == '.json':
                return json.loads(target.read_text(encoding='utf-8'))
            if target.exists() and target.suffix.lower() == '.pdf':
                alt = user_cvs / (target.stem + '.json')
                if alt.exists():
                    return json.loads(alt.read_text(encoding='utf-8'))
        # fallbacks
        for name in ('cv_original.json', 'cv_linkedin_parsed.json'):
            p = user_cvs / name
            if p.exists():
                return json.loads(p.read_text(encoding='utf-8'))
    fallback = Path('static') / 'cv.json'
    if fallback.exists():
        return json.loads(fallback.read_text(encoding='utf-8'))
    return {}


def extract_header_text(pdf_bytes: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        if len(reader.pages) > 0:
            return reader.pages[0].extract_text() or ''
        return ''
    except Exception as e:
        return f'Extraction failed: {e}'


with app.app_context():
    job = Job.query.get(398)
    if not job:
        print('Job 398 not found in DB')
        sys.exit(1)
    cv_data = resolve_user_cv(job)
    suggestions = {'cv_title': cv_data.get('basics', {}).get('label',''), 'summary': cv_data.get('basics', {}).get('summary',''), 'highlighted_work_indices': [], 'highlighted_skill_names': []}
    pdf_bytes = generate_tailored_cv_pdf_bytes(job=job, cv_data=cv_data, suggestions=suggestions)
    # build pretty name
    pretty = build_cv_pdf_filename(job)
    # sanitize simple
    import re
    safe = re.sub(r'[\\/:*?"<>|]+', ' ', pretty).strip()
    if not safe.lower().endswith('.pdf'):
        safe = safe + '.pdf'
    user_dir = Path(app.static_folder) / 'uploads' / 'users' / str(job.user_id) / 'generated'
    user_dir.mkdir(parents=True, exist_ok=True)
    pretty_path = user_dir / safe
    pretty_path.write_bytes(pdf_bytes)
    print('Wrote:', pretty_path)
    header = extract_header_text(pdf_bytes)
    print('--- header ---')
    print(header[:1000])


