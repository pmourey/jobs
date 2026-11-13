#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Model import Job
from tools.document_tools import generate_cover_letter_pdf_bytes
from io import BytesIO

from tools.document_tools import resolve_cover_letter_template_path

with open('/dev/null') as fh:
    pass

# simple test: generate cover letter PDF bytes for job 398
from flask_app import app
with app.app_context():
    job = Job.query.get(398)
    if not job:
        print('Job 398 not found')
        sys.exit(1)
    template = resolve_cover_letter_template_path(app.static_folder)
    pdf = generate_cover_letter_pdf_bytes(job=job, template_path=template, letter_date=__import__('datetime').datetime.now())
    # extract first page text
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(BytesIO(pdf))
        text = reader.pages[0].extract_text() or ''
    except Exception as e:
        text = f'Extraction failed: {e}'
    print('--- cover letter header preview ---')
    print(text.split('\n')[:8])

