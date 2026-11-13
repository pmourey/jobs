"""Catalogue des fournisseurs IA et stockage chiffré des clés utilisateur."""
from __future__ import annotations

import json
import os
from datetime import datetime

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from flask import current_app

from Model import AppSetting, UserAiCredential, db


AI_PROVIDERS = {
    'gemini': {
        'name': 'Google Gemini API',
        'kind': 'openai_compatible',
        'base_url': 'https://generativelanguage.googleapis.com',
        'default_model': 'gemini-2.0-flash',
        'models': ['gemini-3.5-flash-lite', 'gemini-2.0-flash', 'gemini-1.5-flash'],
        'requires_key': True,
        'help_url': 'https://ai.google.dev/gemini-api/docs/api-key',
    },
    'openai': {
        'name': 'OpenAI API',
        'kind': 'openai_compatible',
        'base_url': 'https://api.openai.com',
        'default_model': 'gpt-4o-mini',
        'models': ['gpt-4o-mini', 'gpt-4.1-mini'],
        'requires_key': True,
        'help_url': 'https://platform.openai.com/api-keys',
    },
    'mistral': {
        'name': 'Mistral API',
        'kind': 'openai_compatible',
        'base_url': 'https://api.mistral.ai',
        'default_model': 'mistral-small-latest',
        'models': ['mistral-small-latest', 'mistral-large-latest'],
        'requires_key': True,
        'help_url': 'https://console.mistral.ai/api-keys/',
    },
    'openrouter': {
        'name': 'OpenRouter',
        'kind': 'openai_compatible',
        'base_url': 'https://openrouter.ai/api',
        'default_model': 'openai/gpt-4o-mini',
        'models': ['openai/gpt-4o-mini', 'google/gemini-2.0-flash-001'],
        'requires_key': True,
        'help_url': 'https://openrouter.ai/keys',
    },
    'groq': {
        'name': 'Groq',
        'kind': 'openai_compatible',
        'base_url': 'https://api.groq.com/openai',
        'default_model': 'llama-3.1-8b-instant',
        'models': ['llama-3.1-8b-instant', 'llama-3.3-70b-versatile'],
        'requires_key': True,
        'help_url': 'https://console.groq.com/keys',
    },
    'ollama': {
        'name': 'Ollama (serveur local)',
        'kind': 'openai_compatible',
        'base_url': 'http://localhost:11434',
        'default_model': 'llama3.2:3b',
        'models': ['llama3.2:3b', 'llama3.1:8b'],
        'requires_key': False,
        'help_url': 'https://ollama.com/',
    },
}

DEFAULT_ENABLED = ('gemini', 'openai', 'mistral', 'openrouter', 'groq')


def enabled_provider_keys() -> set[str]:
    raw = AppSetting.get('ai_enabled_providers')
    if raw is None:
        raw = current_app.config.get('AI_ENABLED_PROVIDERS', ','.join(DEFAULT_ENABLED))
    if isinstance(raw, str):
        try:
            values = json.loads(raw) if raw.strip().startswith('[') else raw.split(',')
        except json.JSONDecodeError:
            values = []
    else:
        values = raw
    return {str(value).strip().lower() for value in (values or []) if str(value).strip() in AI_PROVIDERS}


def provider_options(include_disabled: bool = False) -> list[dict]:
    enabled = enabled_provider_keys()
    return [
        {'key': key, **data, 'enabled': key in enabled}
        for key, data in AI_PROVIDERS.items()
        if include_disabled or key in enabled
    ]


def _cipher() -> Fernet:
    key = current_app.config.get('AI_CREDENTIALS_MASTER_KEY') or os.environ.get(
        'AI_CREDENTIALS_MASTER_KEY', ''
    )
    if not key:
        raise RuntimeError(
            'AI_CREDENTIALS_MASTER_KEY est obligatoire pour enregistrer une clé IA personnelle.'
        )
    try:
        return Fernet(key.encode('ascii') if isinstance(key, str) else key)
    except Exception as exc:
        raise RuntimeError('AI_CREDENTIALS_MASTER_KEY doit être une clé Fernet valide.') from exc


def save_user_credential(user_id: int, provider_key: str, api_key: str | None,
                         model: str | None = None) -> UserAiCredential:
    provider = AI_PROVIDERS.get(provider_key)
    if not provider or provider_key not in enabled_provider_keys():
        raise ValueError('Ce fournisseur IA est désactivé par l’administrateur.')
    if provider['requires_key'] and not (api_key or '').strip():
        raise ValueError('Une clé API est obligatoire pour ce fournisseur.')
    encrypted = _cipher().encrypt(api_key.strip().encode()).decode() if api_key and api_key.strip() else None
    credential = UserAiCredential.query.filter_by(user_id=user_id).first()
    if credential is None:
        credential = UserAiCredential(user_id=user_id)
        db.session.add(credential)
    credential.provider_key = provider_key
    credential.encrypted_api_key = encrypted
    credential.model = (model or '').strip() or provider['default_model']
    credential.updated_at = datetime.utcnow()
    db.session.commit()
    return credential


def delete_user_credential(user_id: int) -> None:
    credential = UserAiCredential.query.filter_by(user_id=user_id).first()
    if credential:
        db.session.delete(credential)
        db.session.commit()


def _decrypt(credential: UserAiCredential) -> str:
    if not credential.encrypted_api_key:
        return ''
    return _cipher().decrypt(credential.encrypted_api_key.encode()).decode()


def resolve_user_ai_config(user_id: int) -> dict | None:
    """Retourne la configuration effective sans jamais exposer la clé au template."""
    credential = UserAiCredential.query.filter_by(user_id=user_id).first()
    if credential and credential.provider_key in enabled_provider_keys():
        provider = AI_PROVIDERS[credential.provider_key]
        try:
            api_key = _decrypt(credential)
        except (InvalidToken, RuntimeError, UnicodeDecodeError):
            current_app.logger.warning(
                'Impossible de déchiffrer la clé IA personnelle de user_id=%s; '
                'utilisation de la configuration IA du site.',
                user_id,
            )
        else:
            if provider['requires_key'] and not api_key:
                return None
            credential.last_used_at = datetime.utcnow()
            db.session.commit()
            return {
                'provider_key': credential.provider_key,
                'base_url': provider['base_url'],
                'model': credential.model or provider['default_model'],
                'api_key': api_key or 'ollama-local',
                'site_managed': False,
            }

    base_url = current_app.config.get('GITHUB_MODELS_BASE_URL', '')
    api_key = current_app.config.get('GITHUB_TOKEN', '') or ''
    if not base_url or not api_key:
        return None
    if 'localhost:11434' in base_url or api_key in ('ollama-local', 'OLLAMA_LOCAL'):
        provider_key = 'ollama'
        api_key = 'ollama-local'
    else:
        provider_key = 'gemini' if 'generativelanguage.googleapis.com' in base_url else 'openai'
    return {
        'provider_key': provider_key,
        'base_url': base_url,
        'model': current_app.config.get('GITHUB_MODELS_MODEL', AI_PROVIDERS[provider_key]['default_model']),
        'api_key': api_key,
        'site_managed': True,
    }
