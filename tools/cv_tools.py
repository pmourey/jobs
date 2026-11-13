"""
Outils de génération de CV personnalisé via l'API GitHub Models (IA) et ReportLab.
"""
from __future__ import annotations

import json as _json
import os
import re
from io import BytesIO
from pathlib import Path

from Model import Job


# Small helper to route requests to either the centralized GitHub Models client
# or a local Ollama-compatible endpoint (default localhost:11434). The centralized
# client is preferred; if the project is configured to use a local endpoint and
# the api_key is 'ollama-local', a lightweight HTTP call to the local server is used.
def _model_infer(messages: list, model: str, base_url: str, api_key: str, *,
                 temperature: float = 0.5, max_tokens: int = 512, request_timeout: int = 60, options: dict | None = None):
    """Return the model output string.
    messages: list of {'role':..., 'content':...} for chat-style prompts. If using a local
    Ollama endpoint, messages will be concatenated as a single prompt (system + user).
    """
    # Prefer the centralized wrapper if available
    try:
        from tools.github_models_client import chat_completion
    except Exception:
        chat_completion = None

    is_local = ('localhost' in (base_url or '').lower()) or ('127.0.0.1' in (base_url or '').lower())

    # If configured to use local Ollama by token string, call its REST API directly or force CLI
    if is_local and (api_key == 'ollama-local' or api_key == 'OLLAMA_LOCAL'):
        try:
            import requests

            # Try Ollama /api/chat HTTP endpoint first (fast, native streaming disabled)
            try:
                chat_url = f"{base_url.rstrip('/')}/api/chat"
                chat_options = {
                    'temperature': float(temperature or 0.5),
                    'num_predict': int(max_tokens or 512),
                }
                if options and isinstance(options, dict):
                    chat_options.update(options)
                chat_payload = {
                    'model': model,
                    'messages': messages,
                    'stream': False,
                    'options': chat_options,
                }
                # If JSON output is requested, tell Ollama HTTP API
                all_text = ' '.join(m.get('content', '') for m in messages).lower()
                if 'json' in all_text:
                    chat_payload['format'] = 'json'

                chat_resp = requests.post(chat_url, json=chat_payload, timeout=request_timeout)
                if chat_resp.status_code == 200:
                    chat_json = chat_resp.json()
                    res_content = chat_json.get('message', {}).get('content', '')
                    if res_content:
                        return res_content.strip()
            except Exception as e:
                last_exc = e

            # If the HTTP API failed, do not hang on CLI, try /api/generate as fallback
            cli_forced = False
            last_exc = None

            if cli_forced:
                # Try CLI first
                try:
                    import subprocess, shlex
                    # Build prompt string (concatenate system+user messages)
                    prompt_text = ''
                    for m in messages:
                        role = m.get('role','')
                        content = m.get('content','')
                        if role == 'system':
                            prompt_text += f"[SYSTEM]\n{content}\n\n"
                        else:
                            prompt_text += f"{content}\n\n"
                    cmd = ['ollama', 'run', model, prompt_text, '--format', 'json']
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=request_timeout)
                    if res.returncode == 0 and res.stdout:
                        out = res.stdout.strip()
                        try:
                            idx = out.find('{')
                            if idx != -1:
                                j = _json.loads(out[idx:])
                            else:
                                j = _json.loads(out)
                            text = ''
                            if isinstance(j, dict):
                                if 'response' in j:
                                    text = j.get('response')
                                elif 'output' in j:
                                    text = j.get('output')
                                else:
                                    for v in j.values():
                                        if isinstance(v, str):
                                            text = v
                                            break
                            if not text:
                                return out
                            return (text or '').strip()
                        except Exception:
                            return out
                    # if CLI failed, capture stderr
                    last_exc = Exception(f'CLI failed: rc={res.returncode} stderr={res.stderr.strip()}')
                except Exception as e:
                    last_exc = e

            # If CLI didn't return usable output, fall back to HTTP endpoints
            urls_to_try = [
                f"{base_url.rstrip('/')}/api/predict",
                f"{base_url.rstrip('/')}/api/generate",
                f"{base_url.rstrip('/')}/api/completions",
            ]
            for url in urls_to_try:
                try:
                    resp = requests.post(url, json=payload, timeout=request_timeout)
                    resp.raise_for_status()
                    # Prefer JSON, but accept raw text if JSON parsing fails
                    text = ''
                    try:
                        j = resp.json()
                    except Exception:
                        j = None
                    if isinstance(j, dict):
                        text = j.get('response') or j.get('output') or j.get('text') or ''
                        if not text:
                            results = j.get('results') or j.get('outputs') or j.get('choices')
                            if isinstance(results, list) and results:
                                first = results[0]
                                if isinstance(first, dict):
                                    text = first.get('content') or first.get('text') or first.get('output', '')
                    if not text:
                        # fallback to raw response body
                        text = (resp.text or '')
                    if text:
                        return text
                except Exception as e:
                    last_exc = e
                    continue

            # If none worked, raise last exception to surface issue
            if last_exc:
                raise last_exc
            return ''
        except Exception as e:
            raise

    # If the base_url or model indicates Google Generative AI / Gemini
    lower_url = (base_url or '').lower()
    lower_model = (model or '').lower()
    is_gemini = ('generativelanguage.googleapis.com' in lower_url or
                 (api_key or '').startswith(('AIza', 'AQ.', 'GOOGLE_', 'GEMINI_')) or
                 'gemini' in lower_model or 'google' in lower_url)
    if is_gemini:
        try:
            import requests

            # Map legacy/deprecated model names to modern active Gemini models
            gemini_aliases = {
                'gemini-1.5-pro': 'gemini-3.5-flash-lite',
                'gemini-1.5-flash': 'gemini-3.5-flash-lite',
                'gemini-2.5-pro': 'gemini-3.5-flash-lite',
                'gemini-2.5-flash': 'gemini-3.5-flash-lite',
                'gemini-pro': 'gemini-3.5-flash-lite',
                'gemini-pro-latest': 'gemini-3.5-flash-lite',
                'gemini-flash-latest': 'gemini-3.5-flash-lite',
                'gemini-3.5-flash': 'gemini-3.5-flash-lite',
            }
            requested_model = gemini_aliases.get(model, model) if ('gemini' in lower_model) else 'gemini-3.5-flash-lite'
            models_to_try = [requested_model]
            for candidate in ['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-flash-lite-latest']:
                if candidate not in models_to_try:
                    models_to_try.append(candidate)

            # Build Gemini contents from messages
            contents = []
            system_instruction = None
            for m in messages:
                role = m.get('role', '')
                content = m.get('content', '')
                if role == 'system':
                    system_instruction = {'parts': [{'text': content}]}
                else:
                    contents.append({'role': 'user' if role == 'user' else 'model', 'parts': [{'text': content}]})

            if not contents and system_instruction:
                contents = [{'role': 'user', 'parts': system_instruction['parts']}]

            payload = {
                'contents': contents,
                'generationConfig': {
                    'temperature': float(temperature or 0.5),
                    'maxOutputTokens': max(int(max_tokens or 1500), 1500),
                }
            }
            if system_instruction:
                payload['systemInstruction'] = system_instruction

            all_text = ' '.join(m.get('content', '') for m in messages).lower()
            if 'json' in all_text:
                payload['generationConfig']['responseMimeType'] = 'application/json'

            params = {}
            headers = {'Content-Type': 'application/json'}

            actual_key = api_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY', '')
            if actual_key and not actual_key.startswith(('ollama', 'github_pat')):
                params['key'] = actual_key
            else:
                # Try Bearer token if ADC is available
                try:
                    from google.auth.transport.requests import Request
                    from google.oauth2 import service_account
                    sac = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
                    if sac and os.path.exists(sac):
                        creds = service_account.Credentials.from_service_account_file(sac, scopes=['https://www.googleapis.com/auth/generative-language', 'https://www.googleapis.com/auth/cloud-platform'])
                        creds.refresh(Request())
                        headers['Authorization'] = f"Bearer {creds.token}"
                except Exception:
                    pass

            last_gemini_exc = None
            for g_model in models_to_try:
                try:
                    gemini_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent"
                    resp = requests.post(gemini_endpoint, json=payload, headers=headers, params=params, timeout=request_timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get('candidates', [])
                    if candidates:
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if parts:
                            return parts[0].get('text', '').strip()
                except Exception as g_err:
                    last_gemini_exc = g_err
                    continue

            if last_gemini_exc:
                raise last_gemini_exc
            return ''
        except Exception as e:
            # If Gemini was specifically targeted, do not fall through to invalid endpoints
            if 'generativelanguage.googleapis.com' in lower_url:
                raise
            pass

    # Otherwise try the centralized client if available
    if chat_completion:
        return chat_completion(
            messages=messages,
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            options=options,
        )

    # Last resort: attempt a simple HTTP call compatible with GitHub Models / OpenAI
    try:
        import requests
        url = base_url.rstrip('/')
        # If base_url looks like GitHub Models inference, craft a POST to /v1/chat/completions or similar
        # Try standard OpenAI-compatible endpoint
        if url.endswith('/inference'):
            endpoint = url
        else:
            endpoint = url
        payload = {
            'model': model,
            'messages': messages,
            'temperature': float(temperature or 0.5),
            'max_tokens': int(max_tokens or 512),
        }
        headers = {'Content-Type': 'application/json'}
        if api_key:
            # support Bearer token or simple header name
            headers['Authorization'] = f"Bearer {api_key}"
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=request_timeout)
        resp.raise_for_status()
        try:
            data = resp.json()
            # try to extract usual fields
            if isinstance(data, dict):
                # openai-style
                if 'choices' in data and isinstance(data['choices'], list) and data['choices']:
                    return data['choices'][0].get('message', {}).get('content', '') or data['choices'][0].get('text', '') or ''
                # direct text
                return data.get('data') or data.get('output') or data.get('text') or ''
            return ''
        except Exception:
            return resp.text
    except Exception as e:
        raise


def get_candidate_name_for_job(job: Job) -> str:
    """Retourne le nom complet du candidat propriétaire de l'offre."""
    if not job or not getattr(job, 'user_id', None):
        return ''
    try:
        from flask import current_app
        static_folder = current_app.static_folder
    except Exception:
        static_folder = str(Path(__file__).parent.parent / 'static')

    try:
        info = get_user_contact_info(job.user_id, static_folder)
        if info.get('name'):
            return info['name']
    except Exception:
        pass

    try:
        from Model import User
        u = User.query.get(job.user_id)
        if u and u.username:
            return u.username
    except Exception:
        pass
    return ''


def build_cv_pdf_filename(job: Job) -> str:
    from tools.document_tools import sanitize_filename_part
    company = sanitize_filename_part(job.company) or 'Entreprise'
    title = sanitize_filename_part(job.name) or 'Poste'
    candidate_name = get_candidate_name_for_job(job)
    if candidate_name:
        candidate_part = sanitize_filename_part(candidate_name)
        return f'CV {candidate_part} - {company} - {title}.pdf'
    return f'CV - {company} - {title}.pdf'


def get_user_contact_info(user_id: int, static_folder: str | Path | None = None) -> dict:
    """Extrait les coordonnées de contact (nom, email, téléphone, adresse, code postal, ville)
    depuis le CV par défaut de l'utilisateur ou son compte.
    """
    if static_folder is None:
        try:
            from flask import current_app
            static_folder = current_app.static_folder
        except Exception:
            static_folder = str(Path(__file__).parent.parent / 'static')

    user = None
    try:
        from Model import User
        user = User.query.get(user_id)
    except Exception:
        pass

    cvs_dir = user_cvs_dir(static_folder, user_id)
    basics = {}
    cv_file = None

    if cvs_dir.exists():
        meta_path = cvs_dir / 'cvs_meta.json'
        if meta_path.exists():
            try:
                meta = _json.loads(meta_path.read_text(encoding='utf-8'))
                default = meta.get('_default')
                if default and (cvs_dir / default).exists():
                    target = cvs_dir / default
                    if target.suffix.lower() == '.json':
                        basics = _json.loads(target.read_text(encoding='utf-8')).get('basics', {}) or {}
                        cv_file = default
            except Exception:
                pass
        if not basics:
            for candidate_name in ('cv_gitconnected.json', 'cv_linkedin_parsed.json'):
                p = cvs_dir / candidate_name
                if p.exists():
                    try:
                        basics = _json.loads(p.read_text(encoding='utf-8')).get('basics', {}) or {}
                        if basics:
                            cv_file = candidate_name
                            break
                    except Exception:
                        pass
        if not basics:
            for p in sorted(cvs_dir.glob('*.json')):
                if p.name != 'cvs_meta.json':
                    try:
                        basics = _json.loads(p.read_text(encoding='utf-8')).get('basics', {}) or {}
                        if basics:
                            cv_file = p.name
                            break
                    except Exception:
                        pass

    # Fallback to static/cv.json ONLY for user_id == 1
    if not basics and user_id == 1:
        cv_path = Path(static_folder) / 'cv.json'
        if cv_path.exists():
            try:
                basics = _json.loads(cv_path.read_text(encoding='utf-8')).get('basics', {}) or {}
                cv_file = 'cv.json'
            except Exception:
                pass

    name = (basics.get('name') or (user.username if user else '')).strip()
    email = (basics.get('email') or (user.email if user else '')).strip()
    phone = str(basics.get('phone') or '').strip()

    loc = basics.get('location') or {}
    if isinstance(loc, dict):
        street = loc.get('address') or loc.get('streetAddress') or basics.get('address') or ''
        postal_code = loc.get('postalCode') or loc.get('postal_code') or basics.get('postalCode') or ''
        city = loc.get('city') or loc.get('locality') or loc.get('town') or basics.get('city') or ''
    else:
        street = basics.get('address') or ''
        postal_code = basics.get('postalCode') or ''
        city = basics.get('city') or ''

    if not street and basics.get('address'):
        street = str(basics.get('address')).strip()

    return {
        'user_id': user_id,
        'name': str(name),
        'email': str(email),
        'phone': str(phone),
        'street': str(street).strip(),
        'postal_code': str(postal_code).strip(),
        'city': str(city).strip(),
        'cv_file': cv_file,
    }


def validate_user_contact_info(user_id: int, static_folder: str | Path | None = None) -> tuple[bool, list[str], dict]:
    """Vérifie que les coordonnées obligatoires du candidat (nom, email, tél, adresse, ville) sont renseignées."""
    info = get_user_contact_info(user_id, static_folder)
    missing = []
    if not info.get('name'):
        missing.append('Nom complet')
    if not info.get('email') or '@' not in info.get('email'):
        missing.append('Adresse email')
    if not info.get('phone'):
        missing.append('Numéro de téléphone')
    if not info.get('street'):
        missing.append('Adresse postale')
    if not info.get('city') and not info.get('postal_code'):
        missing.append('Ville')

    is_complete = len(missing) == 0
    return is_complete, missing, info


def save_user_contact_info(user_id: int, contact_data: dict, static_folder: str | Path | None = None) -> bool:
    """Sauvegarde ou met à jour les coordonnées du candidat dans son CV JSON par défaut et dans la table User."""
    if static_folder is None:
        try:
            from flask import current_app
            static_folder = current_app.static_folder
        except Exception:
            static_folder = str(Path(__file__).parent.parent / 'static')

    cvs_dir = user_cvs_dir(static_folder, user_id)
    cvs_dir.mkdir(parents=True, exist_ok=True)
    ensure_canonical_cv(static_folder, user_id)
    meta_path = cvs_dir / 'cvs_meta.json'
    meta = {}
    if meta_path.exists():
        try:
            meta = _json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            meta = {}

    target_filename = CANONICAL_CV_FILENAME
    target_path = cvs_dir / target_filename

    cv_data = {}
    if target_path.exists():
        try:
            cv_data = _json.loads(target_path.read_text(encoding='utf-8'))
        except Exception:
            cv_data = {}

    if not isinstance(cv_data, dict):
        cv_data = {}

    basics = cv_data.setdefault('basics', {})
    if contact_data.get('name') is not None:
        basics['name'] = contact_data['name'].strip()
    if contact_data.get('email') is not None:
        basics['email'] = contact_data['email'].strip()
    if contact_data.get('phone') is not None:
        basics['phone'] = contact_data['phone'].strip()

    loc = basics.setdefault('location', {})
    if not isinstance(loc, dict):
        loc = {}
        basics['location'] = loc

    street = contact_data.get('street', '').strip()
    postal_code = contact_data.get('postal_code', '').strip()
    city = contact_data.get('city', '').strip()

    if street:
        loc['address'] = street
        basics['address'] = street
    if postal_code:
        loc['postalCode'] = postal_code
        basics['postalCode'] = postal_code
    if city:
        loc['city'] = city
        basics['city'] = city

    target_path.write_text(_json.dumps(cv_data, ensure_ascii=False, indent=2), encoding='utf-8')

    if not meta.get('_default') or meta.get('_default') != target_filename:
        meta['_default'] = target_filename
        meta_path.write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')

    if user_id == 1:
        static_cv = Path(static_folder) / 'cv.json'
        if static_cv.exists():
            try:
                s_cv = _json.loads(static_cv.read_text(encoding='utf-8'))
                s_basics = s_cv.setdefault('basics', {})
                if contact_data.get('name'):
                    s_basics['name'] = contact_data['name'].strip()
                if contact_data.get('email'):
                    s_basics['email'] = contact_data['email'].strip()
                if contact_data.get('phone'):
                    s_basics['phone'] = contact_data['phone'].strip()
                s_loc = s_basics.setdefault('location', {})
                if street:
                    s_loc['address'] = street
                    s_basics['address'] = street
                if postal_code:
                    s_loc['postalCode'] = postal_code
                    s_basics['postalCode'] = postal_code
                if city:
                    s_loc['city'] = city
                    s_basics['city'] = city
                static_cv.write_text(_json.dumps(s_cv, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                pass

    try:
        from Model import User, db
        u = User.query.get(user_id)
        if u and contact_data.get('email'):
            new_email = contact_data['email'].strip()
            if new_email and u.email != new_email:
                u.email = new_email
                db.session.commit()
    except Exception:
        try:
            from Model import db
            db.session.rollback()
        except Exception:
            pass

    return True


def user_cvs_dir(static_folder: str | Path, user_id: int) -> Path:
    """Retourne le Path du répertoire cvs pour un utilisateur donné.
    Convention: static/uploads/users/{user_id}/cvs
    """
    return Path(static_folder) / 'uploads' / 'users' / str(user_id) / 'cvs'


CANONICAL_CV_FILENAME = 'cv.json'
CV_SECTIONS = (
    'basics', 'work', 'education', 'skills', 'projects',
    'certificates', 'references', 'languages', 'volunteer',
)


def normalize_cv_data(data: dict | None) -> dict:
    """Retourne un CV JSON Resume avec une structure stable et complète."""
    source = data if isinstance(data, dict) else {}
    basics = source.get('basics')
    normalized = dict(source)
    normalized['basics'] = dict(basics) if isinstance(basics, dict) else {}
    for section in CV_SECTIONS[1:]:
        value = source.get(section)
        normalized[section] = list(value) if isinstance(value, list) else []
    return normalized


def _read_cv_json(path: Path) -> dict:
    try:
        return normalize_cv_data(_json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        return normalize_cv_data({})


def _cv_source_candidates(cvs_dir: Path, meta: dict) -> list[Path]:
    candidates: list[Path] = []
    default_name = meta.get('_default')
    if isinstance(default_name, str):
        default_path = cvs_dir / default_name
        if default_path.suffix.lower() == '.json' and default_path.is_file():
            candidates.append(default_path)
        elif default_path.suffix.lower() == '.pdf':
            parsed = cvs_dir / f'{default_path.stem}.json'
            if parsed.is_file():
                candidates.append(parsed)
    for name in ('cv_linkedin_parsed.json', 'cv_gitconnected.json'):
        path = cvs_dir / name
        if path.is_file() and path not in candidates:
            candidates.append(path)
    candidates.extend(
        path for path in sorted(cvs_dir.glob('*.json'))
        if path.name not in ('cvs_meta.json', CANONICAL_CV_FILENAME) and path not in candidates
    )
    return candidates


def ensure_canonical_cv(static_folder: str | Path, user_id: int) -> Path | None:
    """Crée idempotemment cv.json à partir des anciens CV si nécessaire."""
    cvs_dir = user_cvs_dir(static_folder, user_id)
    cvs_dir.mkdir(parents=True, exist_ok=True)
    canonical = cvs_dir / CANONICAL_CV_FILENAME
    if canonical.is_file():
        normalized = _read_cv_json(canonical)
        canonical.write_text(_json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
        return canonical

    meta_path = cvs_dir / 'cvs_meta.json'
    try:
        meta = _json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
    except (OSError, ValueError):
        meta = {}
    source_paths = _cv_source_candidates(cvs_dir, meta)
    if not source_paths and int(user_id) == 1:
        legacy = Path(static_folder) / 'cv.json'
        if legacy.is_file():
            source_paths = [legacy]
    if not source_paths:
        return None

    source = _read_cv_json(source_paths[0])
    canonical.write_text(_json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
    meta['_default'] = CANONICAL_CV_FILENAME
    meta[CANONICAL_CV_FILENAME] = CANONICAL_CV_FILENAME
    meta_path.write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return canonical


def merge_cv_data(base: dict | None, incoming: dict | None) -> dict:
    """Complète le CV canonique sans remplacer ses valeurs existantes."""
    result = normalize_cv_data(base)
    source = normalize_cv_data(incoming)
    for key, value in source.items():
        if key == 'basics':
            for field, field_value in value.items():
                if not result['basics'].get(field) and field_value:
                    result['basics'][field] = field_value
            continue
        if not isinstance(value, list):
            continue
        existing = result[key]
        for item in value:
            if item not in existing:
                existing.append(item)
    return result


def load_pdf_into_canonical(
    static_folder: str | Path,
    user_id: int,
    pdf_filename: str,
) -> tuple[bool, str]:
    """Extrait un PDF LinkedIn et fusionne ses données dans ``cv.json``."""
    cvs_dir = user_cvs_dir(static_folder, user_id)
    pdf_path = cvs_dir / Path(pdf_filename).name
    if pdf_path.parent != cvs_dir or pdf_path.suffix.lower() != '.pdf' or not pdf_path.is_file():
        return False, 'Le fichier PDF sélectionné est introuvable ou invalide.'

    parsed_path = cvs_dir / f'{pdf_path.stem}.json'
    if not parse_linkedin_pdf_to_json(pdf_path, parsed_path) or not parsed_path.is_file():
        return False, 'Les données du PDF LinkedIn n’ont pas pu être extraites.'
    try:
        incoming = normalize_cv_data(_json.loads(parsed_path.read_text(encoding='utf-8')))
        canonical_path = ensure_canonical_cv(static_folder, user_id)
        base = _read_cv_json(canonical_path) if canonical_path else normalize_cv_data({})
        canonical_path = cvs_dir / CANONICAL_CV_FILENAME
        canonical = merge_cv_data(base, incoming)
        canonical_path.write_text(_json.dumps(canonical, ensure_ascii=False, indent=2), encoding='utf-8')

        meta_path = cvs_dir / 'cvs_meta.json'
        try:
            meta = _json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
        except (OSError, ValueError):
            meta = {}
        meta['_default'] = CANONICAL_CV_FILENAME
        meta[CANONICAL_CV_FILENAME] = CANONICAL_CV_FILENAME
        meta[pdf_path.name] = pdf_path.name
        meta[parsed_path.name] = parsed_path.name
        meta_path.write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    except (OSError, ValueError, TypeError) as exc:
        return False, f'Le JSON extrait du PDF est invalide : {exc}'
    return True, 'Les données du PDF LinkedIn ont été chargées dans le CV canonique.'


def save_cv_json_for_user(static_folder: str | Path, user_id: int, src_json_path: Path, kind: str = 'gitconnected') -> Path:
    """Copie un fichier JSON de CV dans le répertoire utilisateur en appliquant une nomenclature.

    kind peut être: 'gitconnected', 'linkedin_parsed', 'other'.
    Renvoie le path de destination.
    """
    dest_dir = user_cvs_dir(static_folder, user_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    kind_map = {
        'gitconnected': 'cv_gitconnected.json',
        'linkedin_parsed': 'cv_linkedin_parsed.json',
        'other': src_json_path.name,
    }
    dest_name = kind_map.get(kind, 'cv_' + kind + '.json')
    dest = dest_dir / dest_name
    from shutil import copy2
    copy2(src_json_path, dest)
    # update meta
    meta_path = dest_dir / 'cvs_meta.json'
    try:
        import json as _json
        meta = _json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
    except Exception:
        meta = {}
    meta.setdefault(dest_name, dest_name)
    if '_default' not in meta:
        meta['_default'] = dest_name
    meta_path.write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return dest


def parse_linkedin_pdf_to_json(pdf_path: Path, out_json_path: Path) -> bool:
    """Tente de convertir un CV LinkedIn PDF en JSON structuré via le projet
    https://github.com/firedigger/linkedin-resume-parser

    - Si la bibliothèque/module est installé, on l'utilise directement.
    - Sinon, on essaie d'appeler le binaire via subprocess si disponible.

    Retourne True si le fichier JSON de sortie a été généré, False sinon.
    """
    try:
        import sys
        bundled_parser = Path(__file__).parent.parent / 'linkedin-resume-parser'
        if bundled_parser.is_dir() and str(bundled_parser) not in sys.path:
            sys.path.insert(0, str(bundled_parser))
        # Try to import as a module if installed
        from linkedin_resume_parser import parser as lp
        data = lp.parse_pdf(str(pdf_path))
        if isinstance(data, dict):
            out_json_path.write_text(_json.dumps(normalize_cv_data(data), ensure_ascii=False, indent=2), encoding='utf-8')
            return True
    except Exception:
        pass
    try:
        # Try the external CLI when the parser is installed outside the application.
        import subprocess
        subprocess.run(
            ['linkedin-resume-parser', str(pdf_path), '-o', str(out_json_path)],
            check=False,
            timeout=60,
        )
        return out_json_path.exists()
    except Exception:
        pass
    try:
        # Last fallback: PyPDF2 is portable and handles LinkedIn's text-based PDFs.
        import PyPDF2
        reader = PyPDF2.PdfReader(str(pdf_path))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        data = _parse_linkedin_text(text)
        if data['basics'] or any(data[section] for section in CV_SECTIONS[1:]):
            out_json_path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return True
    except Exception:
        pass
    return False


def _parse_linkedin_text(text: str) -> dict:
    """Extrait les sections principales d'un export PDF LinkedIn texte."""
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not re.fullmatch(r'Page \d+ of \d+', line, re.I)]
    headings = {
        'experience': 'work',
        'education': 'education',
        'skills': 'skills',
        'top skills': 'skills',
        'languages': 'languages',
        'certifications': 'certificates',
        'volunteer experience': 'volunteer',
    }
    sections = {section: [] for section in CV_SECTIONS[1:]}
    current = None
    for line in lines:
        key = headings.get(line.casefold())
        if key:
            current = key
            continue
        if line.casefold() in {'contact', 'interests'}:
            current = None
            continue
        if current == 'skills':
            sections['skills'].append({'name': line})
        elif current == 'languages':
            sections['languages'].append({'language': line})
        elif current == 'education':
            sections['education'].append({'institution': line})
        elif current == 'work':
            if not sections['work'] or not sections['work'][-1].get('name'):
                sections['work'].append({'name': line, 'summary': ''})
            else:
                sections['work'][-1]['summary'] += f"{line}\n"

    name = ''
    for index, line in enumerate(lines):
        if line.casefold() == 'languages' and index + 1 < len(lines):
            for candidate in lines[index + 1:index + 8]:
                if candidate.casefold() not in headings and not candidate.startswith('Page '):
                    name = candidate
                    break
            if name:
                break
    return normalize_cv_data({'basics': {'name': name}, **sections})


def load_cv_data(static_folder) -> dict:
    """Charge cv.json depuis le dossier static."""
    cv_path = Path(static_folder) / 'cv.json'
    if not cv_path.exists():
        raise FileNotFoundError(f'cv.json introuvable : {cv_path}')
    with open(cv_path, 'r', encoding='utf-8') as f:
        return _json.load(f)


def _default_cv_suggestions(cv_data: dict, job: Job | None = None) -> dict:
    skills = cv_data.get('skills', [])
    default_projs = ['jobs', 'mini_etl_project']
    if job:
        target_text = f"{job.name or ''} {job.cover_letter_text or ''}".lower()
        if any(w in target_text for w in ['delphi', 'pascal']):
            default_projs = ['Delphi', 'jobs']
        elif any(w in target_text for w in ['data', 'etl', 'donnee', 'données', 'sql', 'base']):
            default_projs = ['jobs', 'mini_etl_project', 'board-games-backend']
        elif any(w in target_text for w in ['linux', 'systeme', 'système', 'devops', 'supervision', 'production', 'bash']):
            default_projs = ['jobs', 'mini_etl_project']
        else:
            default_projs = ['jobs', 'board-games-backend']
    return {
        'cv_title': cv_data.get('basics', {}).get('label', 'Développeur / Consultant IT'),
        'summary': cv_data.get('basics', {}).get('summary', ''),
        'highlighted_work_indices': list(range(min(4, len(cv_data.get('work', []))))),
        'highlighted_skill_names': [s['name'] for s in skills[:6]],
        'highlighted_project_names': default_projs,
        'warning': "Aperçu généré sans IA à cause d'une indisponibilité réseau/API.",
        'source': 'fallback',
    }


# Sections optionnelles disponibles pour le mode avancé
ADVANCED_SECTIONS = {
    'education':      'Formations',
    'certificates':   'Certifications',
    'skills_rating':  'Compétences avec niveau/rating',
    'references':     'Références professionnelles',
    'github_projects': 'Projets GitHub personnels',
}


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc)
    if '429' in text or 'Too Many Requests' in text:
        return True
    response = getattr(exc, 'response', None)
    if response is not None and getattr(response, 'status_code', None) == 429:
        return True
    return getattr(exc, 'status_code', None) == 429


def _build_optional_sections_text(cv_data: dict, include_sections: list,
                                   selected_education: list | None = None,
                                   selected_certificates: list | None = None,
                                   selected_skills: list | None = None,
                                   selected_references: list | None = None,
                                   selected_projects: list | None = None) -> str:
    """Construit le texte des sections optionnelles à injecter dans le prompt IA."""
    has_any = (include_sections or selected_education is not None or selected_certificates is not None
               or selected_skills is not None or selected_references is not None
               or selected_projects is not None)
    if not has_any:
        return ''
    parts = []

    # Formations : filtrées par sélection individuelle si fournie
    if 'education' in include_sections or selected_education is not None:
        education = cv_data.get('education', [])
        if selected_education is not None:
            education = [e for i, e in enumerate(education) if i in selected_education]
        if education:
            lines = []
            for e in education:
                tp = ' - '.join(p for p in [e.get('studyType', ''), e.get('area', '')] if p)
                inst = e.get('institution', '')
                ey = (e.get('endDate') or '')[:4]
                label = tp or inst
                suffix = f' ({inst}, {ey})' if (tp and inst) else (f' ({ey})' if ey else '')
                lines.append(f'  - {label}{suffix}')
            parts.append('Formations :\n' + '\n'.join(lines))

    # Certifications : filtrées par sélection individuelle si fournie
    if 'certificates' in include_sections or selected_certificates is not None:
        certs = cv_data.get('certificates', [])
        if selected_certificates is not None:
            certs = [c for c in certs if c['name'] in selected_certificates]
        if certs:
            lines = [
                f"  - {c['name']} ({c.get('issuer', '')}, {(c.get('date') or '')[:4]})"
                for c in certs
            ]
            parts.append('Certifications :\n' + '\n'.join(lines))

    # Compétences avec niveau, filtrées si sélection individuelle
    if 'skills_rating' in include_sections or selected_skills is not None:
        skills = cv_data.get('skills', [])
        if selected_skills is not None:
            skills = [s for s in skills if s['name'] in selected_skills]
        if skills:
            rating_label = {1: 'Débutant', 2: 'Intermédiaire', 3: 'Avancé', 4: 'Expert'}
            lines = [
                f"  - {s['name']} : {rating_label.get(s.get('rating', 0), s.get('level', 'N/A'))}"
                for s in skills
            ]
            parts.append('Compétences avec niveau :\n' + '\n'.join(lines))

    # Références, filtrées si sélection individuelle
    if 'references' in include_sections or selected_references is not None:
        refs = cv_data.get('references', [])
        if selected_references is not None:
            refs = [r for r in refs if r['name'] in selected_references]
        if refs:
            lines = [
                f"  - {r['name']} : \"{(r.get('reference') or '')[:220].rstrip()}…\""
                for r in refs
            ]
            parts.append('Références professionnelles :\n' + '\n'.join(lines))

    # Projets GitHub, filtrés si sélection individuelle
    if 'github_projects' in include_sections or selected_projects is not None:
        projects = cv_data.get('projects', [])
        if selected_projects is not None:
            projects = [p for p in projects if p['name'] in selected_projects]
        if projects:
            lines = []
            for p in projects[:8]:
                desc = p.get('summary') or p.get('description') or ''
                lang = p.get('primaryLanguage', '')
                lines.append(f"  - {p['name']} [{lang}]{' : ' + desc if desc else ''}")
            parts.append('Projets GitHub personnels :\n' + '\n'.join(lines))

    return ('\n\n' + '\n\n'.join(parts)) if parts else ''


def _build_premium_modules_text(cv_data: dict, selected_premium_modules: list | None = None) -> str:
    """Construit le texte des modules premium optionnels pour la LM."""
    modules = set(selected_premium_modules or [])
    if not modules:
        return ''

    parts = []

    if 'profiles' in modules:
        profiles = cv_data.get('basics', {}).get('profiles', [])
        if profiles:
            lines = []
            for p in profiles:
                network = p.get('network', '')
                url = p.get('url', '')
                username = p.get('username', '')
                lines.append(f"  - {network}: {username} {f'({url})' if url else ''}".strip())
            parts.append('Profils en ligne :\n' + '\n'.join(lines))

    if 'languages' in modules:
        languages = cv_data.get('languages', [])
        if languages:
            lines = [f"  - {lang.get('language', '')} : {lang.get('fluency', '')}" for lang in languages]
            parts.append('Langues :\n' + '\n'.join(lines))

    if 'volunteer' in modules:
        volunteer = cv_data.get('volunteer', [])
        if volunteer:
            lines = []
            for item in volunteer:
                title = ' - '.join(p for p in [item.get('position', ''), item.get('organization', '')] if p)
                summary = (item.get('summary') or '')[:180].replace('\n', ' ')
                lines.append(f'  - {title}{f" : {summary}" if summary else ""}')
            parts.append('Bénévolat :\n' + '\n'.join(lines))

    if 'awards' in modules:
        awards = cv_data.get('awards', [])
        if awards:
            lines = []
            for item in awards:
                name = item.get('title') or item.get('name', '')
                issuer = item.get('awarder') or item.get('issuer', '')
                date = (item.get('date') or '')[:4]
                suffix = ', '.join([p for p in [issuer, date] if p])
                lines.append(f'  - {name}{f" ({suffix})" if suffix else ""}')
            parts.append('Distinctions :\n' + '\n'.join(lines))

    if 'publications' in modules:
        publications = cv_data.get('publications', [])
        if publications:
            lines = []
            for item in publications:
                title = item.get('name') or item.get('title', '')
                publisher = item.get('publisher', '')
                lines.append(f"  - {title}{f' ({publisher})' if publisher else ''}")
            parts.append('Publications :\n' + '\n'.join(lines))

    return ('\n\n' + '\n\n'.join(parts)) if parts else ''


def _is_local_llm_endpoint(base_url: str) -> bool:
    lower = (base_url or '').lower()
    return 'localhost' in lower or '127.0.0.1' in lower


def _get_local_llm_tuning(model_name: str) -> dict:
    try:
        from flask import current_app
        tuning_map = current_app.config.get('OLLAMA_LOCAL_TUNING') or {}
    except Exception:
        tuning_map = {}
    return tuning_map.get(model_name, {})


def _build_core_profile_text(cv_data: dict, is_local_llm: bool) -> str:
    if not isinstance(cv_data, dict):
        return ''

    basics = cv_data.get('basics', {}) or {}
    work = cv_data.get('work', []) or []
    skills = cv_data.get('skills', []) or []

    parts = []

    summary = (basics.get('summary') or '').replace('\n', ' ').strip()
    if summary:
        summary_limit = 180 if is_local_llm else 500
        parts.append(f"Resume candidat : {summary[:summary_limit]}")

    skill_limit = 5 if is_local_llm else 10
    skill_names = [s.get('name') if isinstance(s, dict) else str(s) for s in skills[:skill_limit]]
    skill_names = [name for name in skill_names if name]
    if skill_names:
        parts.append('Competences clefs : ' + ', '.join(skill_names))

    work_limit = 1 if is_local_llm else 4
    work_lines = []
    for item in work[:work_limit]:
        if not isinstance(item, dict):
            continue
        position = item.get('position', '')
        company = item.get('name', '')
        start = (item.get('startDate') or '?')[:4]
        end = (item.get('endDate') or 'present')[:4]
        summary = (item.get('summary') or '').replace('\n', ' ').strip()
        summary_limit = 90 if is_local_llm else 180
        line = f"- {position} chez {company} ({start}-{end})"
        if summary:
            line += f" : {summary[:summary_limit]}"
        work_lines.append(line)
    if work_lines:
        parts.append("Experiences saillantes :\n" + '\n'.join(work_lines))

    return '\n\n'.join(parts)


def _cleanup_cover_letter_output(text: str, author_display: str | None) -> str:
    cleaned = (text or '').strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:text|markdown)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)

    filtered_lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            filtered_lines.append('')
            continue
        if lowered.startswith('voici une lettre de motivation'):
            continue
        if lowered.startswith('voici une proposition de lettre'):
            continue
        if lowered.startswith('titre :'):
            continue
        if lowered.startswith('objet :'):
            continue
        filtered_lines.append(stripped)

    cleaned = '\n'.join(filtered_lines).strip()
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    if cleaned and cleaned[-1] not in '.!?':
        last_sentence_end = max(cleaned.rfind('.'), cleaned.rfind('!'), cleaned.rfind('?'))
        if last_sentence_end > 80:
            cleaned = cleaned[:last_sentence_end + 1].rstrip()

    closing_markers = ('cordialement', 'bien cordialement', 'je vous prie d')
    has_closing = any(marker in cleaned.lower() for marker in closing_markers)
    if cleaned and not has_closing:
        cleaned = (
            cleaned.rstrip()
            + "\n\nJe serais heureux d'echanger avec vous afin de vous presenter plus en detail ma motivation et ma contribution possible a vos projets."
        )

    if author_display and author_display not in cleaned:
        cleaned = cleaned.rstrip() + "\n\nCordialement,\n" + author_display
    return cleaned


def get_ai_cv_suggestions(job: Job, cv_data: dict, github_token: str,
                          ai_base_url: str | None = None,
                          ai_model: str | None = None,
                          additional_prompt: str = '',
                          include_sections: list | None = None,
                          selected_education: list | None = None,
                          selected_certificates: list | None = None,
                          selected_skills: list | None = None,
                          selected_references: list | None = None,
                          selected_projects: list | None = None) -> dict:
    """Appelle l'API GitHub Models pour obtenir des suggestions de personnalisation du CV."""
    from tools.github_models_client import chat_completion
    try:
        from flask import current_app
        base_url = ai_base_url or current_app.config.get('GITHUB_MODELS_BASE_URL', 'https://models.github.ai/inference')
        model_name = ai_model or current_app.config.get('GITHUB_MODELS_MODEL', 'openai/gpt-4.1')
    except Exception:
        base_url = 'https://models.github.ai/inference'
        model_name = 'openai/gpt-4.1'

    inc = list(include_sections or [])
    # Ajouter implicitement 'education'/'certificates' si une sélection individuelle non vide est fournie
    if selected_education and 'education' not in inc:
        inc.append('education')
    if selected_certificates and 'certificates' not in inc:
        inc.append('certificates')
    if selected_skills and 'skills_rating' not in inc:
        inc.append('skills_rating')
    if selected_references and 'references' not in inc:
        inc.append('references')
    if selected_projects and 'github_projects' not in inc:
        inc.append('github_projects')

    work_summary = '\n'.join(
        '[{i}] {pos} chez {co} ({start} - {end}): {summary}'.format(
            i=i,
            pos=w.get('position', ''),
            co=w.get('name', ''),
            start=(w.get('startDate') or '?')[:4],
            end=(w.get('endDate') or 'present')[:4],
            summary=(w.get('summary') or '')[:150].replace('\n', ' '),
        )
        for i, w in enumerate(cv_data.get('work', []))
    )
    skills_summary = ', '.join(s['name'] for s in cv_data.get('skills', []))
    projects_summary = '\n'.join(
        f"  - {p['name']} [{p.get('primaryLanguage', '')}] : {p.get('summary', '')}"
        for p in cv_data.get('projects', [])
    )

    # Sections optionnelles (mode avancé)
    optional_text = _build_optional_sections_text(
        cv_data, inc,
        selected_education=selected_education,
        selected_certificates=selected_certificates,
        selected_skills=selected_skills,
        selected_references=selected_references,
        selected_projects=selected_projects,
    )

    # Instruction spécifique sur l'utilisation des sections additionnelles
    use_optional_instruction = ''
    if inc:
        use_optional_instruction = (
            "IMPORTANT : des données complémentaires ont été fournies ci-dessous. "
            "Utilise-les uniquement comme matière de fond pour adapter le résumé au poste, "
            "sans reprendre les intitulés des rubriques ni énumérer les éléments un par un. "
            "Le résultat doit rester synthétique, naturel et orienté valeur ajoutée.\n\n"
        )

    system_prompt = (
        "Tu es un expert en ressources humaines et en optimisation de CV. "
        "Analyse l offre d emploi et le profil complet du candidat, puis retourne tes recommandations "
        "uniquement sous forme de JSON valide, sans texte supplementaire."
    )
    user_prompt = (
        "{use_optional}"
        "Offre d emploi :\n"
        "- Intitule : {name}\n"
        "- Entreprise : {company}\n"
        "- Localisation : {loc}\n"
        "- LM existante : {lm}\n\n"
        "Experiences du candidat (index entre crochets) :\n{work}\n\n"
        "Competences disponibles : {skills}\n\n"
        "Projets personnels du candidat :\n{projects}"
        "{optional}"
        "\n\n{extra}"
        'Retourne un objet JSON avec exactement ces champs :\n'
        '{{\n'
        '  "cv_title": "titre de CV personnalise en francais (max 80 caracteres)",\n'
        '  "summary": "resume professionnel personnalise en francais (3-4 phrases max 600 caracteres) — intègre les éléments sélectionnés de manière naturelle si pertinents",\n'
        '  "highlighted_work_indices": [liste d entiers : indices des 3-5 experiences les plus pertinentes],\n'
        '  "highlighted_skill_names": [liste de noms de competences les plus pertinentes pour ce poste],\n'
        '  "highlighted_project_names": [liste des 2-3 noms de projets personnels les plus pertinents pour ce poste]\n'
        '}}'
    ).format(
        use_optional=use_optional_instruction,
        name=job.name or 'N/A',
        company=job.company or 'N/A',
        loc=job.zipCode or 'N/A',
        lm=job.cover_letter_text or 'Non precise',
        work=work_summary,
        skills=skills_summary,
        projects=projects_summary,
        optional=optional_text,
        extra=f"Instructions supplementaires : {additional_prompt}\n\n" if additional_prompt else '',
    )

    # Augmenter max_tokens si des sections avancées sont incluses
    max_tokens = 1200 if inc else 900
    is_local_llm = _is_local_llm_endpoint(base_url)
    local_tuning = _get_local_llm_tuning(model_name) if is_local_llm else {}
    # Local CPU inference is much slower; keep output compact to avoid request timeouts.
    if is_local_llm:
        max_tokens = min(max_tokens, local_tuning.get('cv', {}).get('max_tokens', 180))
    request_timeout = local_tuning.get('cv', {}).get('request_timeout', 180) if is_local_llm else 60
    local_options = None
    if is_local_llm:
        local_options = local_tuning.get('options') or {
            'num_thread': int(os.cpu_count() or 8),
            'num_ctx': 2048,
        }

    try:
        raw = _model_infer(
            messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
            model=model_name,
            base_url=base_url,
            api_key=github_token,
            temperature=0.3,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            options=local_options,
        )
    except Exception as exc:
        fallback = _default_cv_suggestions(cv_data, job=job)
        fallback['warning'] = (
            'Trop de requêtes vers le endpoint de modèles. Réessayez dans une minute.' if _is_rate_limit_error(exc)
            else f"Aperçu généré sans IA : {exc}"
        )
        return fallback

    if raw:
        raw = raw.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
    try:
        # Some local endpoints may return already a dict/object; handle gracefully
        if isinstance(raw, dict):
            result = raw
        else:
            result = _json.loads(raw or '{}')
        # Conserver la liste des sections actives pour affichage dans la modale
        result['_active_sections'] = inc
        return result
    except Exception:
        return _default_cv_suggestions(cv_data, job=job)


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extrait le texte d'un PDF si une bibliothèque appropriée est disponible."""
    try:
        import pdfminer.high_level
        return pdfminer.high_level.extract_text(str(pdf_path)) or ''
    except Exception:
        pass
    try:
        import PyPDF2
        text = ''
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ''
        return text
    except Exception:
        return ''


def get_ai_cover_letter_text(job: Job, github_token: str,
                             ai_base_url: str | None = None,
                             ai_model: str | None = None,
                             additional_prompt: str = '',
                             include_sections: list | None = None,
                             selected_education: list | None = None,
                             selected_certificates: list | None = None,
                             selected_skills: list | None = None,
                             selected_references: list | None = None,
                             selected_projects: list | None = None,
                             selected_premium_modules: list | None = None,
                             cv_data: dict | None = None) -> str:
    """Génère une lettre de motivation personnalisée via l'API GitHub Models / OpenAI."""
    # Use the centralized wrapper to call GitHub Models (handles backoff, Retry-After, cache)
    from tools.github_models_client import chat_completion

    try:
        from flask import current_app
        base_url = ai_base_url or current_app.config.get('GITHUB_MODELS_BASE_URL', 'https://models.github.ai/inference')
        model_name = ai_model or current_app.config.get('GITHUB_MODELS_MODEL', 'openai/gpt-4.1')
        static_folder = current_app.static_folder
        is_user_1 = getattr(job, 'user_id', None) == 1
        author_name = current_app.config.get('GMAIL_FULLNAME', '') if is_user_1 else ''
    except Exception:
        base_url = 'https://models.github.ai/inference'
        model_name = 'openai/gpt-4.1'
        static_folder = str(Path(__file__).parent.parent / 'static')
        author_name = ''

    # Charger cv_data pour les sections optionnelles
    if cv_data is None:
        cv_data = {}
        try:
            cv_data = load_cv_data(static_folder)
        except Exception:
            pass

    # Extraire le texte du PDF de capture si disponible
    capture_text = ''
    capture_pdf_path = Path(static_folder) / 'images' / f'capture_{job.id}.pdf'
    if capture_pdf_path.exists():
        try:
            capture_text = _extract_pdf_text(capture_pdf_path)
        except Exception:
            pass

    system_prompt = (
        "Tu es un expert en ressources humaines et en rédaction de lettres de motivation. "
        "Rédige une lettre de motivation professionnelle et personnalisée en français, "
        "structurée en 3 à 4 paragraphes complets. Utilise la première personne du singulier (je/j'), "
        "emploie des phrases complètes et un style soutenu mais naturel. Évite les fragments et les listes à puces. "
        "Corrige les accords et verbes — écris des phrases bien conjuguées (ex. 'J'ai développé', 'J'ai conçu'). "
        "Retourne uniquement le texte final de la lettre, sans titre, sans objet, sans commentaire introductif de type "
        "'Voici une lettre', et sans balisage Markdown.\n\n"
    )

    # Renforcer le system prompt si des sections avancées sont incluses
    inc = list(include_sections or [])
    if selected_education and 'education' not in inc:
        inc.append('education')
    if selected_certificates and 'certificates' not in inc:
        inc.append('certificates')
    if selected_skills and 'skills_rating' not in inc:
        inc.append('skills_rating')
    if selected_references and 'references' not in inc:
        inc.append('references')
    if selected_projects and 'github_projects' not in inc:
        inc.append('github_projects')

    premium_modules = list(selected_premium_modules or [])
    is_local_llm = _is_local_llm_endpoint(base_url)

    if inc:
        system_prompt += (
            "\n\nIMPORTANT : des données complémentaires ont été fournies. "
            "Utilise uniquement les éléments explicitement sélectionnés et reformule-les de façon naturelle. "
            "N'énumère pas les rubriques, n'emploie pas leurs intitulés exacts et évite les citations trop littérales. "
            "La lettre doit rester fluide, générale et orientée sur la valeur apportée au poste."
        )
    if is_local_llm:
        system_prompt += (
            "\n\nPour ce modele local, privilegie une lettre breve et concrete : 2 paragraphes courts, "
            "5 a 7 phrases au total, avec une conclusion simple."
        )
    # Augmenter max_tokens si des sections avancées sont incluses
    max_tokens = 1800 if inc else 1400
    max_tokens = 1800 if inc else 1400
    local_tuning = _get_local_llm_tuning(model_name) if is_local_llm else {}
    if is_local_llm:
        max_tokens = min(max_tokens, local_tuning.get('cover_letter', {}).get('max_tokens', 220))
    request_timeout = local_tuning.get('cover_letter', {}).get('request_timeout', 240) if is_local_llm else 60
    local_options = None
    if is_local_llm:
        local_options = local_tuning.get('options') or {
            'num_thread': int(os.cpu_count() or 8),
            'num_ctx': 2048,
        }

    context_parts = [
        f"Poste : {job.name or 'N/A'}",
        f"Entreprise : {job.company or 'N/A'}",
        f"Localisation : {job.zipCode or 'N/A'}",
    ]
    if job.url:
        context_parts.append(f"Lien de l'offre : {job.url}")
    if capture_text.strip():
        capture_limit = local_tuning.get('cover_letter', {}).get('capture_excerpt_chars', 900)
        capture_excerpt = capture_text.strip()[:capture_limit] if is_local_llm else capture_text.strip()[:2500]
        context_parts.append(
            f"Texte extrait de l'offre (capture PDF) :\n{capture_excerpt}"
        )
    elif job.is_capture:
        context_parts.append("Note : une capture PDF de l'offre est disponible (texte non extractible).")
    if job.cover_letter_text:
        lm_existing_limit = local_tuning.get('cover_letter', {}).get('existing_letter_excerpt_chars', 400)
        lm_existing_excerpt = job.cover_letter_text[:lm_existing_limit] if is_local_llm else job.cover_letter_text[:1200]
        context_parts.append(
            f"Lettre de motivation existante (à améliorer ou à utiliser comme base) :\n{lm_existing_excerpt}"
        )
    core_profile_text = _build_core_profile_text(cv_data, is_local_llm)
    if core_profile_text:
        context_parts.append("Profil candidat :\n" + core_profile_text)

    # Sections optionnelles (mode avancé)
    optional_text = _build_optional_sections_text(
        cv_data, inc,
        selected_education=selected_education,
        selected_certificates=selected_certificates,
        selected_skills=selected_skills,
        selected_references=selected_references,
        selected_projects=selected_projects,
    )
    premium_text = _build_premium_modules_text(cv_data, premium_modules)
    if optional_text.strip():
        context_parts.append("Données complémentaires du profil :" + optional_text)
    if premium_text.strip():
        context_parts.append("Modules premium complémentaires :" + premium_text)

    if additional_prompt:
        context_parts.append(f"Instructions supplémentaires / corrections : {additional_prompt}")

    user_prompt = (
        "Genere la lettre de motivation finale pour ce poste.\n"
        "Contraintes de sortie : pas de titre, pas d'objet, pas d'explication avant ou apres la lettre.\n"
        "Mets l'accent sur l'adequation Python, DevOps, automatisation, Linux et integration applicative.\n\n"
        + "\n\n".join(context_parts)
    )

    # Determine display name for signature: prefer cv_data.basics.name then candidate name from job, then author_name
    author_display = None
    try:
        basics = cv_data.get('basics', {}) if isinstance(cv_data, dict) else {}
        author_display = basics.get('name')
    except Exception:
        author_display = None
    if not author_display and job:
        try:
            author_display = get_candidate_name_for_job(job)
        except Exception:
            pass
    if not author_display:
        author_display = author_name or 'Candidat'

    if not github_token:
        title = job.name or 'ce poste'
        company = job.company or 'votre entreprise'
        base_text = (
            f"Je vous adresse ma candidature pour le poste de {title} au sein de {company}.\n\n"
            "Fort de mon expérience dans le développement logiciel et la gestion de projets IT, "
            "je suis convaincu de pouvoir apporter une réelle valeur ajoutée à votre équipe.\n\n"
            "Je reste à votre disposition pour un entretien afin de vous présenter "
            "plus en détail mon parcours et mes motivations.\n\n"
            "[GITHUB_TOKEN non configuré : texte généré sans IA]"
        )
        if author_display:
            base_text = base_text + "\n" + (author_display or '')
        return base_text

    try:
        raw = _model_infer(
            messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
            model=model_name,
            base_url=base_url,
            api_key=github_token,
            temperature=0.35 if is_local_llm else 0.5,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            options=local_options,
        )
        return _cleanup_cover_letter_output((raw or '').strip(), author_display)
    except Exception as exc:
        # If the models endpoint was removed or returns 410 Gone, fall back to non-AI text
        msg = str(exc)
        if '410' in msg or 'Gone' in msg:
            base_text = (
                f"Je vous adresse ma candidature pour le poste de {job.name or 'ce poste'} au sein de {job.company or 'votre entreprise'}.\n\n"
                "Fort de mon expérience dans le développement logiciel et la gestion de projets IT, "
                "je suis convaincu de pouvoir apporter une réelle valeur ajoutée à votre équipe.\n\n"
                "Je reste à votre disposition pour un entretien afin de vous présenter "
                "plus en détail mon parcours et mes motivations.\n\n"
                "[API IA indisponible : texte généré sans IA]"
            )
            if author_display:
                base_text = base_text + "\n" + (author_display or '')
            return base_text
        if _is_rate_limit_error(exc):
            raise RuntimeError('Trop de requêtes vers le endpoint de modèles. Réessayez dans une minute.') from exc
        raise RuntimeError(f"Erreur API IA lors de la génération de la LM : {exc}") from exc


def generate_tailored_cv_pdf_bytes(job: Job, cv_data: dict, suggestions: dict,
                                   include_sections: list | None = None,
                                   selected_education: list | None = None,
                                   selected_certificates: list | None = None,
                                   selected_skills: list | None = None,
                                   selected_references: list | None = None,
                                   selected_projects: list | None = None) -> bytes:
    """Genere le PDF du CV personnalise avec ReportLab."""
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (HRFlowable, Image, Paragraph,
                                    SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    try:
        from flask import current_app
        static_folder = current_app.static_folder
    except Exception:
        static_folder = str(Path(__file__).parent.parent / 'static')

    # Default sender info (fallback), can be overridden from cv_data.basics when available
    # Ensure values used in PDF header are strings (defensive against malformed JSON where fields may be objects)
    def _safe_str(v):
        if v is None:
            return ''
        if isinstance(v, str):
            return v
        # For dict-like address/location values, try to build a readable string
        if isinstance(v, dict):
            for k in ('address', 'formatted', 'streetAddress', 'street_address'):
                if k in v and v[k]:
                    return str(v[k])
            parts = [p for p in (v.get('street'), v.get('postalCode') or v.get('postal_code') or v.get('postal'), v.get('city') or v.get('locality') or v.get('town'), v.get('region')) if p]
            if parts:
                return ', '.join(map(str, parts))
            try:
                import json as _json
                return _json.dumps(v, ensure_ascii=False)
            except Exception:
                return str(v)
        try:
            import json as _json
            return _json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)

    basics = cv_data.get('basics', {}) if isinstance(cv_data, dict) else {}
    SENDER_NAME = _safe_str(basics.get('name'))
    if not SENDER_NAME:
        try:
            from Model import User
            if job and getattr(job, 'user_id', None):
                u = User.query.get(job.user_id)
                if u and u.username:
                    SENDER_NAME = u.username
        except Exception:
            pass
    SENDER_NAME = SENDER_NAME or 'Candidat'

    # 'location' or 'address' may be composite objects. Extract street-like and city-like parts
    def _extract_street_city(v):
        if not v:
            return ('', '')
        if isinstance(v, str):
            return (v, '')
        if isinstance(v, dict):
            # try common keys for street/address and city/postal
            street_keys = ('streetAddress', 'street_address', 'street', 'address', 'formatted')
            street = ''
            for k in street_keys:
                if k in v and v.get(k):
                    street = v.get(k)
                    break
            # compose city with postal if available
            city_parts = []
            for k in ('postalCode', 'postal_code', 'postal'):
                if k in v and v.get(k):
                    city_parts.append(str(v.get(k)))
            for k in ('city', 'locality', 'town', 'region'):
                if k in v and v.get(k):
                    city_parts.append(str(v.get(k)))
                    break
            city = ' '.join(city_parts).strip()
            return (_safe_str(street) or '', _safe_str(city) or '')
        # list or other
        try:
            return (' '.join(map(str, v)), '')
        except Exception:
            return (str(v), '')

    addr_src = basics.get('address') or basics.get('location')
    street_val, city_val = _extract_street_city(addr_src)
    addr_str = _safe_str(basics.get('address') or (addr_src.get('address') if isinstance(addr_src, dict) else ''))
    SENDER_STREET = street_val or (addr_str if addr_str else '')
    if city_val and addr_str and str(city_val).strip() and str(city_val).strip() in addr_str:
        SENDER_CITY = ''
    else:
        SENDER_CITY = city_val or _safe_str(basics.get('city')) or ''
    location = basics.get('location') if isinstance(basics.get('location'), dict) else {}
    postal_code = _safe_str(
        basics.get('postalCode') or basics.get('postal_code')
        or location.get('postalCode') or location.get('postal_code')
    ).strip()
    if postal_code and postal_code not in SENDER_CITY:
        SENDER_CITY = f'{postal_code} {SENDER_CITY}'.strip()
    SENDER_PHONE = _safe_str(basics.get('phone')) or ''
    SENDER_EMAIL = _safe_str(basics.get('email'))
    if not SENDER_EMAIL:
        try:
            from Model import User
            if job and getattr(job, 'user_id', None):
                u = User.query.get(job.user_id)
                if u and u.email:
                    SENDER_EMAIL = u.email
        except Exception:
            pass
    SENDER_EMAIL = SENDER_EMAIL or ''
    PHOTO_WIDTH = 2.5 * cm

    COLOR_DARK = rl_colors.HexColor('#1a1a2e')
    COLOR_BLUE = rl_colors.HexColor('#4a90d9')
    COLOR_GREY = rl_colors.HexColor('#555555')
    COLOR_LGREY = rl_colors.HexColor('#cccccc')

    page_w, page_h = A4
    lm = rm = 1.8 * cm
    tm = 0.8 * cm
    bm = 0.8 * cm
    avail_w = page_w - lm - rm

    _counter = [0]

    def _st(base_name, **kw):
        _counter[0] += 1
        name = f'{base_name}_{_counter[0]}'
        d = dict(fontName='Helvetica', fontSize=9.5, leading=13,
                 textColor=rl_colors.black, alignment=TA_LEFT)
        d.update(kw)
        return ParagraphStyle(name, **d)

    st_name = _st('nm', fontName='Helvetica-Bold', fontSize=15, leading=16, textColor=COLOR_DARK)
    st_title = _st('ti', fontName='Helvetica-Oblique', fontSize=10.5, leading=13, textColor=COLOR_BLUE)
    st_contact = _st('co', fontSize=8.5, leading=11, textColor=COLOR_GREY)
    st_icon = _st('ic', fontSize=10.5, leading=12, textColor=COLOR_GREY)
    st_section = _st('se', fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=COLOR_BLUE)
    st_jt = _st('jt', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=COLOR_DARK)
    st_jc = _st('jc', fontSize=8.5, leading=11, textColor=COLOR_GREY)
    st_body = _st('bo', fontSize=9, leading=12, alignment=TA_JUSTIFY)
    st_hlblue = _st('hl', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=COLOR_BLUE)
    st_edu = _st('ed', fontName='Helvetica-Bold', fontSize=9, leading=12)
    st_edu_sub = _st('es', fontSize=8.5, leading=11, textColor=COLOR_GREY)

    story = []
    cv_title = suggestions.get('cv_title') or cv_data.get('basics', {}).get('label', '')

    # Prefer user-specific uploaded photo if present: static/uploads/users/{user_id}/photo.jpg
    photo_path = None
    try:
        owner_id = getattr(job, 'user_id', None)
        if owner_id is not None:
            candidate = Path(static_folder) / 'uploads' / 'users' / str(owner_id) / 'photo.jpg'
            if candidate.exists():
                photo_path = candidate
    except Exception:
        photo_path = None
    name_cell = [
        Paragraph(SENDER_NAME, st_name),
        Spacer(1, 4),
        Paragraph(cv_title, st_title),
        Spacer(1, 6),
        Paragraph(SENDER_STREET, st_contact),
        Paragraph(SENDER_CITY, st_contact),
        Paragraph(f'Tél.\u00a0: {SENDER_PHONE}', st_contact),
        Paragraph(f'Email\u00a0: {SENDER_EMAIL}', st_contact),
    ]
    rqth_label = cv_data.get('basics', {}).get('rqth') or cv_data.get('basics', {}).get('status')
    if rqth_label:
        name_cell.append(Spacer(1, 2))
        name_cell.append(Paragraph(f'<b>Statut\u00a0:</b> {rqth_label}', st_contact))

    if photo_path and photo_path.exists():
        try:
            from PIL import Image as PILImage
            pil_img = PILImage.open(str(photo_path))
            orig_w, orig_h = pil_img.size
            photo_height = PHOTO_WIDTH * orig_h / orig_w
            photo_img = Image(str(photo_path), width=PHOTO_WIDTH, height=photo_height)
            hdr_data = [[name_cell, photo_img]]
            hdr_cols = [None, PHOTO_WIDTH + 0.2 * cm]
        except Exception:
            hdr_data = [[name_cell]]
            hdr_cols = [None]
    else:
        hdr_data = [[name_cell]]
        hdr_cols = [None]

    hdr_table = Table(hdr_data, colWidths=hdr_cols)
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 5))
    story.append(HRFlowable(width='100%', thickness=0.5, color=COLOR_LGREY))
    story.append(Spacer(1, 8))

    # Profil
    summary = suggestions.get('summary') or cv_data.get('basics', {}).get('summary', '')
    if summary:
        story.append(Paragraph('PROFIL', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        story.append(Paragraph(summary, st_body))
        story.append(Spacer(1, 9))

    # Experiences
    work_list = cv_data.get('work', [])
    hl_indices = set(suggestions.get('highlighted_work_indices') or [])
    hl_work = [w for i, w in enumerate(work_list) if i in hl_indices]
    other_work = [w for i, w in enumerate(work_list) if i not in hl_indices]
    sorted_work = hl_work + other_work

    if sorted_work:
        story.append(Paragraph('EXPERIENCES PROFESSIONNELLES', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        for idx, work in enumerate(sorted_work[:8]):
            is_hl = work in hl_work
            pos = work.get('position', '')
            co = work.get('name', '')
            start = (work.get('startDate') or '')[:7]
            end = (work.get('endDate') or '')[:7] or 'present'
            loc = work.get('location', '')
            story.append(Paragraph(pos, st_hlblue if is_hl else st_jt))
            parts = [p for p in [co, (start + ' - ' + end if start else ''), loc] if p]
            story.append(Paragraph(' | '.join(parts), st_jc))
            wtext = work.get('summary', '')
            if wtext:
                for line in [ln.strip() for ln in wtext.split('\n') if ln.strip()][:2]:
                    story.append(Paragraph('\u2022 ' + line, st_body))
            hls = work.get('highlights', [])
            if hls:
                story.append(Paragraph('<i>Techn. : ' + hls[0] + '</i>', st_edu_sub))
            if idx < len(sorted_work[:8]) - 1:
                story.append(Spacer(1, 5))
        story.append(Spacer(1, 9))

    # Competences
    skills = cv_data.get('skills', [])
    if selected_skills is not None:
        skills = [s for s in skills if s.get('name') in selected_skills]
    hl_skill_names = set(suggestions.get('highlighted_skill_names') or [])
    if skills:
        story.append(Paragraph('COMPETENCES', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        hl_sk = [s for s in skills if s['name'] in hl_skill_names]
        other_sk = [s for s in skills if s['name'] not in hl_skill_names]
        all_sk = hl_sk + other_sk
        n_cols = 3
        rows = []
        for j in range(0, len(all_sk), n_cols):
            cells = []
            for s in all_sk[j:j + n_cols]:
                if s['name'] in hl_skill_names:
                    cells.append(Paragraph(
                        '<b>\u2605 ' + s['name'] + '</b>',
                        _st('skh', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=COLOR_BLUE),
                    ))
                else:
                    cells.append(Paragraph(
                        '\u25cb ' + s['name'],
                        _st('skn', fontSize=9, leading=12),
                    ))
            while len(cells) < n_cols:
                cells.append(Paragraph('', st_body))
            rows.append(cells)
        if rows:
            sk_t = Table(rows, colWidths=[avail_w / n_cols] * n_cols)
            sk_t.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            story.append(sk_t)
        story.append(Spacer(1, 9))

    # Formation
    # Si selected_education est fourni : afficher uniquement les entrées sélectionnées
    # Sinon : afficher toutes les entrées (comportement original, sans limite de 4)
    all_education = cv_data.get('education', [])
    if selected_education is not None:
        education_to_show = [all_education[i] for i in selected_education if i < len(all_education)]
    else:
        education_to_show = all_education  # toutes les formations
    if education_to_show:
        story.append(Paragraph('FORMATION', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        for edu in education_to_show:
            tp = [p for p in [edu.get('studyType', ''), edu.get('area', '')] if p]
            story.append(Paragraph(' - '.join(tp) or edu.get('institution', ''), st_edu))
            ey = (edu.get('endDate') or '')[:4]
            story.append(Paragraph(edu.get('institution', '') + (' (' + ey + ')' if ey else ''), st_edu_sub))
            desc = edu.get('description', '')
            if desc:
                story.append(Paragraph(f'<i>{desc}</i>', st_edu_sub))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 9))

    # Certifications & Langues
    # Si selected_certificates est fourni : afficher uniquement les certifications sélectionnées
    all_certs = cv_data.get('certificates', [])
    if selected_certificates is not None:
        certs = [c for c in all_certs if c['name'] in selected_certificates]
    else:
        certs = all_certs  # toutes les certifications
    languages = cv_data.get('languages', [])
    left_c: list = []
    right_c: list = []

    if certs:
        left_c.append(Paragraph('CERTIFICATIONS', st_section))
        left_c.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        left_c.append(Spacer(1, 4))
        for c in certs:
            yr = (c.get('date') or '')[:4]
            left_c.append(Paragraph(
                '\u2022 ' + c['name'] + ' (' + c.get('issuer', '') + ', ' + yr + ')',
                st_body,
            ))
    if languages:
        right_c.append(Paragraph('LANGUES', st_section))
        right_c.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        right_c.append(Spacer(1, 4))
        for lang in languages:
            right_c.append(Paragraph(
                '\u2022 ' + lang['language'] + ' - ' + lang.get('fluency', ''),
                st_body,
            ))

    if left_c or right_c:
        if not left_c:
            left_c = [Paragraph('', st_body)]
        if not right_c:
            right_c = [Paragraph('', st_body)]
        bot = Table([[left_c, right_c]], colWidths=[avail_w * 0.6, avail_w * 0.4])
        bot.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(bot)
        story.append(Spacer(1, 9))

    inc = include_sections or suggestions.get('_active_sections') or []
    all_projects = cv_data.get('projects', [])

    # Sélection intelligente des projets personnels :
    # 1. Sélection manuelle spécifique cochée par l'utilisateur
    if selected_projects is not None:
        projects_to_show = [p for p in all_projects if p.get('name') in selected_projects]
    # 2. Section 'github_projects' cochée globalement
    elif 'github_projects' in inc:
        projects_to_show = all_projects[:6]
    # 3. Par défaut (si aucune case optionnelle n'est cochée) :
    # inclure automatiquement les projets les mieux adaptés à l'offre
    elif not include_sections:
        hl_names = suggestions.get('highlighted_project_names') or []
        if hl_names:
            projects_to_show = [p for p in all_projects if p.get('name') in hl_names]
        else:
            job_text = f"{job.name or ''} {job.cover_letter_text or ''}".lower()
            if any(k in job_text for k in ['delphi', 'pascal']):
                chosen = ['Delphi', 'jobs']
            elif any(k in job_text for k in ['data', 'etl', 'donnee', 'données', 'sql', 'base']):
                chosen = ['jobs', 'mini_etl_project', 'board-games-backend']
            elif any(k in job_text for k in ['linux', 'systeme', 'système', 'devops', 'supervision', 'production', 'bash']):
                chosen = ['jobs', 'mini_etl_project']
            else:
                chosen = ['jobs', 'board-games-backend']
            projects_to_show = [p for p in all_projects if p.get('name') in chosen]
    else:
        projects_to_show = []

    if projects_to_show:
        story.append(Paragraph('PROJETS PERSONNELS & RÉALISATIONS', st_section))
        story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
        story.append(Spacer(1, 4))
        for p in projects_to_show[:3]:
            langs = p.get('languages') or ([p['primaryLanguage']] if p.get('primaryLanguage') else [])
            lang_str = ', '.join(langs[:4]) if langs else ''
            disp_name = p.get('displayName') or p.get('name')
            proj_url = p.get('url') or p.get('githubUrl') or ''
            title_line = disp_name + (f' [{lang_str}]' if lang_str else '')
            story.append(Paragraph('\u2022 ' + title_line, st_jt))
            desc = p.get('summary') or p.get('description') or ''
            if desc:
                story.append(Paragraph(desc[:220], st_body))
            if proj_url:
                story.append(Paragraph(f'<link href="{proj_url}">{proj_url}</link>',
                                       _st('lk', fontSize=7.5, leading=10, textColor=COLOR_BLUE)))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 9))

    # Section Références (si cochée en mode avancé)
    if 'references' in inc or selected_references is not None:
        refs = cv_data.get('references', [])
        if selected_references is not None:
            refs = [r for r in refs if r.get('name') in selected_references]
        if refs:
            story.append(Paragraph('RÉFÉRENCES PROFESSIONNELLES', st_section))
            story.append(HRFlowable(width='100%', thickness=0.3, color=COLOR_LGREY))
            story.append(Spacer(1, 4))
            for ref in refs:
                story.append(Paragraph(ref.get('name', ''), st_jt))
                ref_text = (ref.get('reference') or '')[:350].rstrip()
                if len(ref.get('reference', '')) > 350:
                    ref_text += '\u2026'
                story.append(Paragraph(f'\u201c{ref_text}\u201d',
                                       _st('rf', fontSize=8.5, leading=11, textColor=COLOR_GREY,
                                           alignment=__import__('reportlab.lib.enums', fromlist=['TA_JUSTIFY']).TA_JUSTIFY)))
                story.append(Spacer(1, 6))
            story.append(Spacer(1, 9))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=lm, rightMargin=rm, topMargin=tm, bottomMargin=bm,
        title=build_cv_pdf_filename(job), author=SENDER_NAME,
    )
    doc.build(story)
    return buffer.getvalue()
