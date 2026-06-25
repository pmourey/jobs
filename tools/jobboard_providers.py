"""
Clients minimalistes pour fournisseurs d'API d'offres : Greenhouse, Lever, Ashby, Teamtailor.
But : fournir des adaptateurs simples réutilisables pour intégrer ces sources dans les recherches.
- Chaque client expose : search_offers(params) -> list[dict]
- Ces implémentations sont des adaptateurs/boîtes à outils : elles lisent les variables de config
  depuis `os.environ` (clé API / endpoint) et retournent une liste d'offres au format interne attendu
  (dicts contenant au minimum : id, intitule/title, entreprise/company, lieu/location, url).

Note : ce fichier fournit des implémentations basiques/stub qui peuvent être utilisées hors réseau
(en mode fallback) ou étendues pour un déploiement réel. Les appels HTTP sont faits avec `requests`.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests


class ProviderError(RuntimeError):
    pass


def _safe_get(d: dict, *keys, default=''):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


class BaseProvider:
    name: str = 'base'

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get(f'{self.name.upper()}_API_KEY')
        self.base_url = base_url or os.environ.get(f'{self.name.upper()}_BASE_URL')

    def _headers(self) -> dict:
        h = {'Accept': 'application/json'}
        if self.api_key:
            h['Authorization'] = f'Bearer {self.api_key}'
        return h

    def search_offers(self, q: Optional[str] = None, **params) -> List[Dict[str, Any]]:
        raise NotImplementedError


class GreenhouseProvider(BaseProvider):
    name = 'greenhouse'

    def search_offers(self, q: Optional[str] = None, **params) -> List[Dict[str, Any]]:
        """
        Greenhouse usually exposes a public jobs feed per company (no central search API) or
        via partner APIs. This method attempts to query an exposed jobs endpoint if configured.
        Expected env:
         - GREENHOUSE_BASE_URL (ex: https://boards.greenhouse.io/company_name)
        """
        # If no base_url configured, return empty list (fallback)
        if not self.base_url:
            return []
        # Try several common patterns: /jobs.json, /positions, or embed HTML containing JSON
        tried = []
        jobs = []
        errors = []
        patterns = ['/jobs.json', '/positions.json', '/positions', '/jobs']
        for p in patterns:
            try:
                url = self.base_url.rstrip('/') + p
                tried.append(url)
                r = requests.get(url, headers=self._headers(), timeout=8)
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                # try JSON
                try:
                    data = r.json()
                    jobs = data.get('jobs') or data.get('positions') or data or []
                    if jobs:
                        break
                except Exception:
                    # Maybe HTML embed; attempt to extract JSON inside a script tag
                    text = r.text
                    import re as _re
                    m = _re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', text, _re.S|_re.M)
                    if not m:
                        m = _re.search(r'var jobs = (\[\{.+?\}\]);', text, _re.S|_re.M)
                    if m:
                        try:
                            jobs = _json.loads(m.group(1))
                            if jobs:
                                break
                        except Exception:
                            pass
            except Exception as exc:
                errors.append(str(exc))
                continue
            results = []
            for j in jobs:
                results.append({
                    'id': str(j.get('id') or j.get('job_id') or j.get('internal_job_id') or j.get('title')),
                    'intitule': j.get('title'),
                    'entreprise': _safe_get(j, 'location', 'office') or _safe_get(j, 'company'),
                    'lieu': _safe_get(j.get('location', {}) if isinstance(j.get('location'), dict) else {}, 'name') or '',
                    'url': j.get('absolute_url') or j.get('url') or url,
                    'dateCreation': j.get('created_at') or j.get('posted_at') or '',
                    'raw': j,
                })
            return results
        # If we fellthrough with no jobs, raise helpful error
        if not jobs:
            raise ProviderError(f'Greenhouse: no jobs found for tried URLs: {tried} errors: {errors}')
        return results


class LeverProvider(BaseProvider):
    name = 'lever'

    def search_offers(self, q: Optional[str] = None, **params) -> List[Dict[str, Any]]:
        """
        Lever provides company-specific APIs like https://api.lever.co/v0/postings/{company}
        Expected env:
         - LEVER_BASE_URL (ex: https://api.lever.co/v0/postings)
         - LEVER_COMPANY (company identifier appended)
        """
        company = params.get('company') or os.environ.get('LEVER_COMPANY')
        if not self.base_url and not company:
            return []
        try:
            if self.base_url:
                url = self.base_url.rstrip('/')
                if company:
                    url = f"{url}/{company}"
            else:
                url = f"https://api.lever.co/v0/postings/{company}"
            r = requests.get(url, headers=self._headers(), timeout=8, params={'mode': 'json'})
            r.raise_for_status()
            data = r.json()
            results = []
            for j in data:
                results.append({
                    'id': str(j.get('id') or j.get('postingId') or j.get('title')),
                    'intitule': j.get('title'),
                    'entreprise': (j.get('company') or _safe_get(j, 'categories', {}).get('team')
                                   if isinstance(j.get('categories'), dict) else j.get('categories')),
                    'lieu': _safe_get(j.get('categories', {}), 'location') or j.get('location') or '',
                    'url': j.get('hostedUrl') or j.get('applyUrl') or '',
                    'dateCreation': j.get('createdAt') or '',
                    'raw': j,
                })
            return results
        except Exception as exc:
            raise ProviderError(f'Lever fetch failed: {exc}') from exc


class AshbyProvider(BaseProvider):
    name = 'ashby'

    def search_offers(self, q: Optional[str] = None, **params) -> List[Dict[str, Any]]:
        """
        Ashby has partner APIs; this is a best-effort adapter.
        Env:
         - ASHBY_BASE_URL
         - ASHBY_API_KEY
        """
        if not self.base_url:
            return []
        try:
            url = self.base_url.rstrip('/') + '/jobs'
            headers = self._headers()
            # Ashby may use X-API-Key or Bearer token depending on deployment
            if self.api_key and 'Authorization' not in headers:
                headers['X-API-Key'] = self.api_key
            r = requests.get(url, headers=headers, timeout=8, params={'q': q} if q else None)
            r.raise_for_status()
            data = r.json()
            items = data.get('data') or data.get('jobs') or []
            results = []
            for j in items:
                results.append({
                    'id': str(j.get('id') or j.get('jobId') or j.get('externalId') or j.get('title')),
                    'intitule': j.get('title') or j.get('name'),
                    'entreprise': _safe_get(j, 'company', 'employer') or '',
                    'lieu': _safe_get(j, 'location') or '',
                    'url': j.get('apply_url') or j.get('url') or '',
                    'dateCreation': j.get('created_at') or j.get('posted_at') or '',
                    'raw': j,
                })
            return results
        except Exception as exc:
            raise ProviderError(f'Ashby fetch failed: {exc}') from exc


class TeamtailorProvider(BaseProvider):
    name = 'teamtailor'

    def search_offers(self, q: Optional[str] = None, **params) -> List[Dict[str, Any]]:
        """
        Teamtailor exposes company-specific job feeds, often at {company}.teamtailor.com/positions
        Env:
         - TEAMTAILOR_BASE_URL (ex: https://company.teamtailor.com)
        """
        if not self.base_url:
            return []
        try:
            # Aggressive discovery: try root and several common JSON endpoints,
            # then fall back to HTML parsing (JSON-LD, window.__INITIAL_STATE__, var jobs = ...)
            candidates = []
            tried = []
            patterns = ['/', '/positions', '/jobs', '/jobs.json', '/positions.json', '/api/v1/jobs', '/api/v1/positions']
            import re as _re
            import json as _json
            for path in patterns:
                try:
                    url = self.base_url.rstrip('/') + path
                    tried.append(url)
                    headers = self._headers()
                    if self.api_key and 'Authorization' not in headers:
                        headers['Authorization'] = f'Bearer {self.api_key}'
                    r = requests.get(url, headers=headers, timeout=8)
                    if r.status_code == 404:
                        continue
                    r.raise_for_status()
                    # Try JSON response first
                    try:
                        data = r.json()
                        if isinstance(data, dict):
                            items = data.get('positions') or data.get('jobs') or data.get('data') or []
                        else:
                            items = data
                        if items:
                            candidates.extend(items if isinstance(items, list) else [items])
                            break
                    except Exception:
                        text = r.text
                        # 1) JSON-LD
                        ld_matches = _re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text, _re.S | _re.I)
                        for blk in ld_matches:
                            try:
                                obj = _json.loads(blk)
                                if isinstance(obj, list):
                                    candidates.extend(obj)
                                else:
                                    # if it's a JobPosting or contains job items
                                    if obj.get('@type') == 'JobPosting' or 'JobPosting' in str(obj):
                                        candidates.append(obj)
                                    else:
                                        # try to find nested lists
                                        if isinstance(obj, dict):
                                            for k in ('positions', 'jobs', 'items', 'offers'):
                                                v = obj.get(k)
                                                if v:
                                                    if isinstance(v, list):
                                                        candidates.extend(v)
                                                    else:
                                                        candidates.append(v)
                            except Exception:
                                # ignore parse errors for this block and continue
                                pass
                        if candidates:
                            break
                        # 2) window.__INITIAL_STATE__ or similar
                        m = _re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', text, _re.S | _re.M)
                        if not m:
                            m = _re.search(r'var\s+initialState\s*=\s*(\{.*?\});', text, _re.S | _re.M)
                        if m:
                            try:
                                jsobj = _json.loads(m.group(1))
                                # walk to find job lists
                                def _walk(d):
                                    if isinstance(d, dict):
                                        for k, v in d.items():
                                            if k.lower() in ('positions', 'jobs', 'listings', 'items') and isinstance(v, (list, dict)):
                                                return v
                                            res = _walk(v)
                                            if res:
                                                return res
                                    elif isinstance(d, list):
                                        for it in d:
                                            res = _walk(it)
                                            if res:
                                                return res
                                    return None
                                found = _walk(jsobj)
                                if found:
                                    if isinstance(found, list):
                                        candidates.extend(found)
                                    else:
                                        candidates.append(found)
                            except Exception:
                                pass
                        if candidates:
                            break
                        # 3) var jobs = [...] pattern
                        m2 = _re.search(r'var\s+jobs\s*=\s*(\[\{.+?\}\]);', text, _re.S | _re.M)
                        if m2:
                            try:
                                arr = _json.loads(m2.group(1))
                                candidates.extend(arr)
                            except Exception:
                                pass
                        if candidates:
                            break
                except Exception:
                    continue
            results = []
            for j in candidates:
                results.append({
                    'id': str(j.get('id') or j.get('uuid') or j.get('slug') or j.get('title')),
                    'intitule': j.get('title') or j.get('name'),
                    'entreprise': _safe_get(j, 'company', 'employer') or '',
                    'lieu': _safe_get(j, 'location') or '',
                    'url': j.get('absolute_url') or j.get('apply_url') or j.get('url') or j.get('permalink') or '',
                    'dateCreation': j.get('published_at') or j.get('created_at') or '',
                    'raw': j,
                })
            return results
        except Exception as exc:
            raise ProviderError(f'Teamtailor fetch failed: {exc}') from exc


class SmartRecruitersProvider(BaseProvider):
    name = 'smartrecruiters'

    def search_offers(self, q: Optional[str] = None, **params) -> List[Dict[str, Any]]:
        """
        Basic adapter for SmartRecruiters public jobs/search endpoints.
        Env:
         - SMARTRECRUITERS_BASE_URL (optional) or provide base_url param
         - SMARTRECRUITERS_API_KEY (optional)
        Docs: https://developers.smartrecruiters.com/
        """
        base = self.base_url or os.environ.get('SMARTRECRUITERS_BASE_URL')
        if not base:
            # Use public search endpoint
            url = 'https://api.smartrecruiters.com/v1/companies'
        else:
            url = base.rstrip('/')
        headers = self._headers()
        # SmartRecruiters may require an API key in X-Api-Key
        if self.api_key and 'Authorization' not in headers:
            headers['X-Api-Key'] = self.api_key
        try:
            # If a company identifier is provided, try company jobs
            company = params.get('company') or os.environ.get('SMARTRECRUITERS_COMPANY')
            if company:
                url = f'https://api.smartrecruiters.com/v1/companies/{company}/jobs'
                r = requests.get(url, headers=headers, timeout=8, params={'search': q} if q else None)
                r.raise_for_status()
                data = r.json()
                items = data.get('content') or data.get('jobs') or []
            else:
                # Global search (may be limited); try /search-postings
                url = 'https://api.smartrecruiters.com/v1/search/postings'
                r = requests.get(url, headers=headers, timeout=8, params={'q': q} if q else None)
                r.raise_for_status()
                data = r.json()
                items = data.get('content') or data.get('postings') or []
            results = []
            for j in items:
                results.append({
                    'id': str(j.get('id') or j.get('postingId') or j.get('uuid') or j.get('title')),
                    'intitule': j.get('title') or j.get('position') or j.get('name'),
                    'entreprise': _safe_get(j, 'company', 'employer') or '',
                    'lieu': _safe_get(j, 'location') or j.get('location', {}).get('city') or '',
                    'url': j.get('applyUrl') or j.get('links', {}).get('self') or j.get('permalink') or '',
                    'dateCreation': j.get('publicationDate') or j.get('createdAt') or '',
                    'raw': j,
                })
            return results
        except Exception as exc:
            raise ProviderError(f'SmartRecruiters fetch failed: {exc}') from exc


# Convenience factory
def get_provider(name: str, **kwargs) -> BaseProvider:
    name_l = (name or '').lower()
    if name_l == 'greenhouse':
        return GreenhouseProvider(**kwargs)
    if name_l == 'lever':
        return LeverProvider(**kwargs)
    if name_l == 'ashby':
        return AshbyProvider(**kwargs)
    if name_l in ('teamtailor', 'team-tailor'):
        return TeamtailorProvider(**kwargs)
    if name_l in ('smartrecruiters', 'smart-recruiters'):
        return SmartRecruitersProvider(**kwargs)
    raise ValueError(f'Unknown provider: {name}')









