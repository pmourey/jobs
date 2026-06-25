"""Outils utilitaires pour importer un CV depuis différentes sources.

Fonctionnalités minimales:
- parse_json_cv(raw_bytes) -> dict : parse et valide JSON GitConnected
- fetch_linkedin_profile(url) -> dict : tentative de récupération d'un profil LinkedIn
  (placeholder / best-effort). Retourne dict ou lève une exception.

Remarque: LinkedIn n'autorise généralement pas le scraping. Cette fonction essaie
une requête simple mais doit être utilisée avec prudence. Préférez l'export JSON
via GitConnected ou une API officielle si disponible.
"""
from __future__ import annotations

import json
import requests
from typing import Optional


def parse_json_cv(raw: bytes) -> dict:
    """Parse raw bytes en JSON et retourne le dict.

    Lève ValueError si invalide.
    """
    try:
        data = json.loads(raw.decode('utf-8'))
    except Exception as exc:
        raise ValueError(f'JSON invalide: {exc}')
    # Minimal sanity checks
    if not isinstance(data, dict):
        raise ValueError('Le JSON du CV doit être un objet racine.')
    if 'basics' not in data:
        # Not strictly required but helpful
        raise ValueError('Le JSON semble incomplet (clé "basics" absente).')
    return data


def fetch_linkedin_profile(url: str, timeout: int = 5) -> dict:
    """Tentative simple de récupération du HTML public et extraction basique.

    ATTENTION: LinkedIn bloque souvent les requêtes non authentifiées. Cette
    fonction fait un essai basique et retourne une structure minimale si elle
    parvient à récupérer un contenu. En cas d'échec elle lève RuntimeError.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; JobsApp/1.0; +https://example.com)'
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except Exception as exc:
        raise RuntimeError(f"Impossible de récupérer l'URL LinkedIn: {exc}")
    if r.status_code != 200:
        raise RuntimeError(f"LinkedIn returned status {r.status_code}")
    html = r.text
    # Very basic extraction: try to find the <title> as name
    name = None
    import re
    m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
    if m:
        name = m.group(1).split('|')[0].strip()
    # Build a minimal CV-like dict
    cv = {
        'basics': {
            'name': name or '',
            'source': 'linkedin',
            'source_url': url,
        },
        'raw_html': html[:2000],  # keep a snippet only
    }
    return cv

