"""Client centralisé pour appels GitHub Models / OpenAI-compatible.

Fournit:
- chat_completion(...) : wrapper avec backoff exponentiel, respect de Retry-After,
  et cache simple en mémoire (TTL configurable).
"""
from __future__ import annotations

import time
import threading
# functools.wraps not needed
from typing import Any

_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
_BLOCK_UNTIL = 0


def _cache_get(key: str) -> Any:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        value, expire = entry
        if expire and time.time() > expire:
            del _CACHE[key]
            return None
        return value


def _cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    expire = time.time() + ttl if ttl else None
    with _CACHE_LOCK:
        _CACHE[key] = (value, expire)


def chat_completion(messages: list[dict], model: str, base_url: str, api_key: str,
                    max_tokens: int = 1000, temperature: float = 0.3,
                    response_format: dict | None = None, cache_ttl: int = 30) -> str:
    """Effectue une completion chat vers l'endpoint OpenAI-compatible.

    - Implémente retry/backoff pour 429 et erreurs réseau.
    - Cache les réponses identiques pendant ``cache_ttl`` secondes.
    - Retourne le texte brut (string) de la réponse (content).
    """
    import hashlib
    import json
    import requests

    key = hashlib.sha256(json.dumps({
        'model': model,
        'messages': messages,
        'response_format': response_format,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }, sort_keys=True).encode('utf-8')).hexdigest()

    cached = _cache_get(key)
    if cached is not None:
        return cached

    url = base_url.rstrip('/') + '/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    if response_format:
        payload['response_format'] = response_format

    # Retry/backoff
    backoff = 1.0
    for attempt in range(6):
        try:
            global _BLOCK_UNTIL
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            # Global block if another caller set a long Retry-After previously
            if time.time() < _BLOCK_UNTIL:
                raise RuntimeError('Blocked due to previous rate-limit; retry after block expires')
            if r.status_code == 200:
                data = r.json()
                # compatibilité avec structure attendue
                try:
                    content = data['choices'][0]['message']['content']
                except Exception:
                    # fallback generic
                    content = data.get('choices', [{}])[0].get('text') if isinstance(data.get('choices'), list) else ''
                _cache_set(key, content, ttl=cache_ttl)
                return content
            elif r.status_code == 429:
                # Respect Retry-After header; if large, set a global block to avoid hammering
                retry = r.headers.get('Retry-After')
                timerem = r.headers.get('x-ratelimit-timeremaining') or r.headers.get('x-ratelimit-reset')
                try:
                    wait = float(retry) if retry else backoff
                except Exception:
                    wait = backoff
                # If Retry-After is large (>60s), set a global block until that time
                if retry:
                    try:
                        _BLOCK_UNTIL = time.time() + float(retry)
                    except Exception:
                        _BLOCK_UNTIL = time.time() + wait
                time.sleep(wait)
                backoff = min(backoff * 2, 300)
                continue
            else:
                r.raise_for_status()
        except requests.exceptions.RequestException as exc:
            # Network error -> backoff
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            last_exc = exc
            continue
    # Si on arrive ici, raise last exception
    raise RuntimeError(f"API call failed after retries: {locals().get('last_exc', 'unknown')}")


