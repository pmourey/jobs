#!/usr/bin/env python3
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Model import Job
from tools.cv_tools import load_cv_data, generate_tailored_cv_pdf_bytes, get_ai_cv_suggestions, build_cv_pdf_filename

from io import BytesIO

def find_user_cv(user_id: int):
    user_dir = Path('static') / 'uploads' / 'users' / str(user_id) / 'cvs'
    meta = {}
    if user_dir.exists():
        meta_path = user_dir / 'cvs_meta.json'
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding='utf-8'))
            except Exception:
                meta = {}
        default = meta.get('_default')
        if default:
            target = user_dir / default
            if target.exists() and target.suffix.lower() == '.json':
                return json.loads(target.read_text(encoding='utf-8'))
            # try parsed sibling
            alt = user_dir / (target.stem + '.json')
            if alt.exists():
                return json.loads(alt.read_text(encoding='utf-8'))
        # fallbacks
        for name in ('cv_original.json', 'cv_linkedin_parsed.json'):
            p = user_dir / name
            if p.exists():
                return json.loads(p.read_text(encoding='utf-8'))
    # final fallback to static/cv.json
    fallback = Path('static') / 'cv.json'
    if fallback.exists():
        return json.loads(fallback.read_text(encoding='utf-8'))
    raise FileNotFoundError('No CV JSON found for user')


def extract_header_text(pdf_bytes: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        text = ''
        # Extract only first page
        if len(reader.pages) > 0:
            text = reader.pages[0].extract_text() or ''
        return text
    except Exception as e:
        print('PyPDF2 extraction failed:', e)
        return ''


def main():
    user_id = 1
    cv_data = find_user_cv(user_id)
    # create a minimal Job-like object
    class SimpleJob:
        def __init__(self):
            self.id = 9999
            self.user_id = user_id
            self.name = 'Test Role'
            self.company = 'Test Company'
            self.zipCode = 'N/A'
            self.cover_letter_text = ''
            self.is_capture = False
            self.url = ''
    job = SimpleJob()
    suggestions = {'cv_title': cv_data.get('basics', {}).get('label',''), 'summary': cv_data.get('basics', {}).get('summary',''), 'highlighted_work_indices': [], 'highlighted_skill_names': []}
    pdf_bytes = generate_tailored_cv_pdf_bytes(job=job, cv_data=cv_data, suggestions=suggestions)
    header_text = extract_header_text(pdf_bytes)
    print('--- PDF header text (first page) ---')
    print(header_text[:4000])

if __name__ == '__main__':
    main()


