import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

import flask_app
from flask_app import app
from Model import User, db
from tools.cv_tools import (
    extract_cv_text,
    normalize_cv_data,
    normalize_cv_date,
    validate_cv_data,
)


def test_supplied_user_7_pdf_is_extracted_and_converted(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[1] / 'CV-CPC-Jean-Paul Ferreira.pdf'
    if not source.is_file():
        pytest.skip('CV fourni absent')
    with app.app_context():
        user = db.session.get(User, 7)
        if user is None:
            pytest.skip('Utilisateur 7 absent de la base de test')

    extracted = extract_cv_text(source)
    assert 'Jean-Paul FERREIRA' in extracted

    monkeypatch.setattr(
        flask_app,
        'resolve_user_ai_config',
        lambda user_id: {
            'api_key': 'test-key',
            'base_url': 'https://example.test',
            'model': 'test-model',
            'site_managed': True,
        },
    )
    monkeypatch.setattr(flask_app, '_consume_site_ai_quota', lambda user_id, config: (True, ''))
    monkeypatch.setattr(
        flask_app,
        'convert_cv_text_with_ai',
        lambda text, config: {
            'basics': {'name': 'Jean-Paul FERREIRA'},
            'work': [{'name': 'Expérience extraite'}],
        },
    )
    monkeypatch.setattr(app, 'static_folder', str(tmp_path / 'static'))

    client = app.test_client()
    with client.session_transaction() as session:
        session['login_id'] = 7
    response = client.post(
        '/import_cv',
        data={'user_id': '7', 'cv_file': (io.BytesIO(source.read_bytes()), source.name)},
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert response.status_code == 200
    assert response.get_json()['ok'] is True

    cvs_dir = Path(app.static_folder) / 'uploads' / 'users' / '7' / 'cvs'
    canonical = json.loads((cvs_dir / 'cv.json').read_text(encoding='utf-8'))
    assert canonical['basics']['name'] == 'Jean-Paul FERREIRA'
    archived = list((cvs_dir / 'originals').glob('*.pdf'))
    assert len(archived) == 1

    preview = client.get(f"/cv_original/7/{archived[0].name}")
    assert preview.status_code == 200
    assert preview.mimetype == 'application/pdf'

    shutil.rmtree(Path(app.static_folder), ignore_errors=True)


def test_docx_and_odt_text_extraction(tmp_path):
    from docx import Document

    docx_path = tmp_path / 'resume.docx'
    document = Document()
    document.add_paragraph('Jean-Paul Ferreira')
    document.add_paragraph('Responsable qualité')
    document.save(docx_path)
    assert 'Responsable qualité' in extract_cv_text(docx_path)

    odt_path = tmp_path / 'resume.odt'
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        '<office:body><office:text><text:h>Jean-Paul Ferreira</text:h>'
        '<text:p>Responsable qualité</text:p></office:text></office:body></office:document-content>'
    )
    with zipfile.ZipFile(odt_path, 'w') as archive:
        archive.writestr('content.xml', content)
    assert 'Responsable qualité' in extract_cv_text(odt_path)


def test_cv_dates_are_normalized_for_date_inputs():
    assert normalize_cv_date('15/03/2022') == '2022-03-15'
    assert normalize_cv_date('Mars 2021') == '2021-03-01'
    assert normalize_cv_date('2020-06') == '2020-06-01'
    assert normalize_cv_date('Présent', 'endDate') == ''
    data = normalize_cv_data({
        'work': [{'startDate': 'septembre 2019', 'endDate': 'Aujourd’hui'}],
        'certificates': [{'date': '2021/11/05'}],
    })
    assert data['work'][0] == {'startDate': '2019-09-01', 'endDate': ''}
    assert data['certificates'][0]['date'] == '2021-11-05'


def test_cv_validation_reports_minimum_required_fields():
    warnings = validate_cv_data({
        'basics': {'name': 'Jean-Paul FERREIRA'},
        'work': [{'position': 'Pharmacien', 'startDate': ''}],
        'education': [{'area': 'Pharmacie', 'endDate': ''}],
    })
    assert 'Expérience 1 : nom de l’entreprise manquant.' in warnings
    assert 'Expérience 1 : date de début manquante.' in warnings
    assert 'Formation 1 : organisme de formation manquant.' in warnings
    assert 'Formation 1 : date de diplôme manquante.' in warnings


def test_user_cv_resolver_loads_canonical_sections(tmp_path, monkeypatch):
    canonical_dir = tmp_path / 'static' / 'uploads' / 'users' / '7' / 'cvs'
    canonical_dir.mkdir(parents=True)
    (canonical_dir / 'cv.json').write_text(json.dumps({
        'basics': {'name': 'Jean-Paul FERREIRA'},
        'education': [{'institution': 'FOR DRUG CONSULTING'}],
    }), encoding='utf-8')
    monkeypatch.setattr(app, 'static_folder', str(tmp_path / 'static'))
    with app.app_context():
        resolved = flask_app._resolve_user_cv_data(7)
    assert resolved['basics']['name'] == 'Jean-Paul FERREIRA'
    assert resolved['education'][0]['institution'] == 'FOR DRUG CONSULTING'


def test_unified_json_upload_updates_canonical_and_archives_original(monkeypatch, tmp_path):
    with app.app_context():
        if db.session.get(User, 7) is None:
            pytest.skip('Utilisateur 7 absent de la base de test')
    monkeypatch.setattr(app, 'static_folder', str(tmp_path / 'static'))
    client = app.test_client()
    with client.session_transaction() as session:
        session['login_id'] = 7

    response = client.post(
        '/import_cv',
        data={
            'user_id': '7',
            'cv_file': (
                io.BytesIO(json.dumps({'basics': {'name': 'CV JSON'}}).encode()),
                'resume.json',
            ),
        },
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert response.status_code == 200
    cvs_dir = Path(app.static_folder) / 'uploads' / 'users' / '7' / 'cvs'
    assert json.loads((cvs_dir / 'cv.json').read_text())['basics']['name'] == 'CV JSON'
    assert len(list((cvs_dir / 'originals').glob('*.json'))) == 1

    response = client.post(
        '/import_cv',
        data={
            'user_id': '7',
            'cv_file': (
                io.BytesIO(json.dumps({'basics': {'name': 'CV JSON remplacé'}}).encode()),
                'resume-2.json',
            ),
        },
        content_type='multipart/form-data',
        headers={'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
    )
    assert response.status_code == 200
    assert json.loads((cvs_dir / 'cv.json').read_text())['basics']['name'] == 'CV JSON remplacé'
    assert len(list((cvs_dir / 'originals').glob('*'))) == 1
