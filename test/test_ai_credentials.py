from datetime import datetime

from cryptography.fernet import Fernet

from flask_app import app, db
from Model import AppSetting, User, UserAiCredential
from tools.ai_credentials import delete_user_credential, resolve_user_ai_config, save_user_credential


def test_personal_ai_key_is_encrypted_and_deleted():
    app.config['TESTING'] = True
    app.config['AI_CREDENTIALS_MASTER_KEY'] = Fernet.generate_key().decode()
    app.config['AI_ENABLED_PROVIDERS'] = 'gemini'
    with app.app_context():
        db.create_all()
        suffix = str(int(datetime.now().timestamp() * 1000000))
        user = User(
            username=f'ai_{suffix}',
            password='password',
            creation_date=datetime.now(),
            email=f'ai_{suffix}@example.com',
        )
        db.session.add(user)
        db.session.commit()
        try:
            credential = save_user_credential(user.id, 'gemini', 'secret-api-key', 'gemini-test')
            assert 'secret-api-key' not in credential.encrypted_api_key
            resolved = resolve_user_ai_config(user.id)
            assert resolved['api_key'] == 'secret-api-key'
            assert resolved['model'] == 'gemini-test'
            AppSetting.set('ai_enabled_providers', '[]')
            assert resolve_user_ai_config(user.id) is None
            delete_user_credential(user.id)
            assert UserAiCredential.query.filter_by(user_id=user.id).first() is None
        finally:
            AppSetting.query.filter_by(key='ai_enabled_providers').delete()
            db.session.delete(user)
            db.session.commit()


def test_invalid_personal_key_falls_back_to_site_ai():
    previous_config = {
        key: app.config.get(key)
        for key in (
            'TESTING',
            'AI_CREDENTIALS_MASTER_KEY',
            'AI_ENABLED_PROVIDERS',
            'GITHUB_MODELS_BASE_URL',
            'GITHUB_MODELS_MODEL',
            'GITHUB_TOKEN',
        )
    }
    app.config['TESTING'] = True
    app.config['AI_CREDENTIALS_MASTER_KEY'] = Fernet.generate_key().decode()
    app.config['AI_ENABLED_PROVIDERS'] = 'gemini'
    app.config['GITHUB_MODELS_BASE_URL'] = 'https://models.example.test/v1'
    app.config['GITHUB_MODELS_MODEL'] = 'site-model'
    app.config['GITHUB_TOKEN'] = 'site-api-key'
    with app.app_context():
        db.create_all()
        suffix = str(int(datetime.now().timestamp() * 1000000))
        user = User(
            username=f'ai_invalid_{suffix}',
            password='password',
            creation_date=datetime.now(),
            email=f'ai_invalid_{suffix}@example.com',
        )
        db.session.add(user)
        db.session.commit()
        try:
            save_user_credential(user.id, 'gemini', 'personal-api-key')
            app.config['AI_CREDENTIALS_MASTER_KEY'] = Fernet.generate_key().decode()

            resolved = resolve_user_ai_config(user.id)

            assert resolved['site_managed'] is True
            assert resolved['api_key'] == 'site-api-key'
            assert resolved['model'] == 'site-model'
        finally:
            db.session.delete(user)
            db.session.commit()
            for key, value in previous_config.items():
                if value is None:
                    app.config.pop(key, None)
                else:
                    app.config[key] = value
