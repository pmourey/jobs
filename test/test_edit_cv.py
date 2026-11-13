import json
import shutil
from datetime import datetime
from pathlib import Path

from flask_app import app, db
from Model import User


def test_edit_cv_updates_structured_json():
    app.config['TESTING'] = True
    with app.app_context():
        suffix = str(int(datetime.now().timestamp() * 1000000))
        user = User(
            username=f'cv_editor_{suffix}',
            password='password',
            creation_date=datetime.now(),
            email=f'cv_editor_{suffix}@example.com',
        )
        db.session.add(user)
        db.session.commit()

        user_dir = Path(app.static_folder) / 'uploads' / 'users' / str(user.id)
        cvs_dir = user_dir / 'cvs'
        cvs_dir.mkdir(parents=True, exist_ok=True)
        cv_path = cvs_dir / 'cv_editable.json'
        cv_path.write_text(json.dumps({'basics': {'name': 'Avant'}, 'work': []}), encoding='utf-8')

        client = app.test_client()
        with client.session_transaction() as session:
            session['login_id'] = user.id

        response = client.get(f'/edit_cv/{user.id}?file={cv_path.name}')
        assert response.status_code == 200

        response = client.post(
            f'/edit_cv/{user.id}',
            data={
                'file': cv_path.name,
                'name': 'Après',
                'label': 'Développeur',
                'email': '',
                'phone': '',
                'summary': '',
                'location_address': '',
                'location_postalCode': '',
                'location_city': '',
                'location_country': '',
                'work': '[{"position": "Développeur"}]',
                'education': '[]',
                'skills': '[]',
                'projects': '[]',
                'certificates': '[]',
                'languages': '[]',
                'volunteer': '[]',
                'references': '[]',
            },
        )
        assert response.status_code == 302

        saved = json.loads(cv_path.read_text(encoding='utf-8'))
        assert saved['basics']['name'] == 'Après'
        assert saved['work'][0]['position'] == 'Développeur'

        db.session.delete(user)
        db.session.commit()
        shutil.rmtree(user_dir, ignore_errors=True)
