import io
import json
import os
from pathlib import Path
from datetime import datetime

import pytest

from flask_app import app, db
from Model import User
from tools.cv_tools import ensure_canonical_cv


def make_test_user(username='testuser', email='test@example.com'):
    # ensure unique username/email in test DB by appending timestamp
    suffix = str(int(datetime.now().timestamp() * 1000))
    uname = f"{username}_{suffix}"
    emailu = f"{username}_{suffix}@example.com"
    u = User(username=uname, password='x', creation_date=datetime.now(), email=emailu)
    db.session.add(u)
    db.session.commit()
    return u



def test_import_linkedin_pdf_updates_canonical_cv(tmp_path, monkeypatch):
    client = app.test_client()
    with app.app_context():
        user = make_test_user(username='importpdf2', email='importpdf2@example.com')
        cvs_dir = Path(app.static_folder) / 'uploads' / 'users' / str(user.id) / 'cvs'
        if cvs_dir.exists():
            for f in cvs_dir.iterdir():
                try:
                    f.unlink()
                except Exception:
                    pass
        cvs_dir.mkdir(parents=True, exist_ok=True)

        def fake_parse(src_path, dest_path):
            sample = {'basics': {'name': 'Parsed LinkedIn', 'label': 'Dev'}}
            Path(dest_path).write_text(json.dumps(sample, ensure_ascii=False), encoding='utf-8')
            return True

        monkeypatch.setattr('tools.cv_tools.parse_linkedin_pdf_to_json', fake_parse)

        with client.session_transaction() as sess:
            sess['login_id'] = user.id

        data = {
            'user_id': str(user.id),
            'cv_pdf': (io.BytesIO(b'%PDF-1.4 test'), 'linkedin_profile.pdf')
        }

        response = client.post(
            '/import_cv',
            data=data,
            content_type='multipart/form-data',
            headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        )
        assert response.status_code == 200
        assert response.get_json()['ok'] is True

        canonical = cvs_dir / 'cv.json'
        assert not canonical.exists()
        load_response = client.post(
            f'/load_pdf_to_canonical/{user.id}',
            data={'file': 'linkedin_profile.pdf'},
            follow_redirects=False,
        )
        assert load_response.status_code == 302
        assert canonical.exists()
        normalized = json.loads(canonical.read_text(encoding='utf-8'))
        assert normalized['basics']['name'] == 'Parsed LinkedIn'
        assert normalized['work'] == []
        meta = json.loads((cvs_dir / 'cvs_meta.json').read_text(encoding='utf-8'))
        assert meta['_default'] == 'cv.json'


def test_legacy_cv_is_migrated_to_canonical(tmp_path):
    with app.app_context():
        user = make_test_user(username='legacycv', email='legacycv@example.com')
        cvs_dir = Path(app.static_folder) / 'uploads' / 'users' / str(user.id) / 'cvs'
        cvs_dir.mkdir(parents=True, exist_ok=True)
        legacy = cvs_dir / 'cv_linkedin_parsed.json'
        legacy.write_text(json.dumps({'basics': {'name': 'Legacy'}, 'skills': [{'name': 'Python'}]}), encoding='utf-8')

        canonical = ensure_canonical_cv(app.static_folder, user.id)
        assert canonical is not None
        data = json.loads(canonical.read_text(encoding='utf-8'))
        assert data['basics']['name'] == 'Legacy'
        assert data['education'] == []
        assert json.loads((cvs_dir / 'cvs_meta.json').read_text(encoding='utf-8'))['_default'] == 'cv.json'





