"""
Client API France Travail v2 pour la recherche d'offres d'emploi.

Authentification : OAuth2 client_credentials
Documentation : https://francetravail.io/produits-partages/catalogue/offres-emploi/documentation
Base URL : https://api.francetravail.io/partenaire/offresdemploi/v2
Token URL : https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from requests.exceptions import ProxyError, RequestException

logger = logging.getLogger(__name__)

# Le domaine d'authentification est .fr (pas .io) — realm intégré dans l'URL comme requis par l'API
FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
FT_API_BASE  = "https://api.francetravail.io/partenaire/offresdemploi/v2"
FT_SCOPE     = "api_offresdemploiv2 o2dsoffre"

# Codes types de contrat France Travail (validés API v2 — IND/CUI/PRO causent 400)
CONTRACT_TYPES: dict[str, str] = {
    "CDI": "CDI – Contrat à durée indéterminée",
    "CDD": "CDD – Contrat à durée déterminée",
    "MIS": "Mission intérimaire",
    "SAI": "Saisonnier",
    "LIB": "Libéral / indépendant",
    "FRA": "Franchise",
}

# Modes de travail (libellés API France Travail)
WORK_MODES: dict[str, str] = {
    "": "Tous les modes",
    "Présentiel": "Présentiel",
    "Hybride": "Hybride",
    "Télétravail": "Télétravail complet",
}

# Départements de référence
DEPARTMENTS: dict[str, str] = {
    "": "Toute la France",
    "06": "Alpes-Maritimes (06)",
    "13": "Bouches-du-Rhône (13)",
    "83": "Var (83)",
    "84": "Vaucluse (84)",
    "75": "Paris (75)",
    "69": "Rhône (69)",
    "33": "Gironde (33)",
    "31": "Haute-Garonne (31)",
    "59": "Nord (59)",
    "67": "Bas-Rhin (67)",
    "34": "Hérault (34)",
    "92": "Hauts-de-Seine (92)",
    "78": "Yvelines (78)",
    "38": "Isère (38)",
}

# Mots-clés ATS optimisés pour le profil IT/DevOps/Sécurité de Philippe Mourey
# Conformes aux standards ATS modernes (termes exacts utilisés par les recruteurs)
ATS_KEYWORDS_PROFILE: list[str] = [
    "Ingénieur DevOps",
    "Ingénieur Systèmes Linux",
    "Ingénieur Sécurité Cybersécurité",
    "Site Reliability Engineer SRE",
    "Docker Kubernetes Cloud Native",
    "Python Scripting Automation",
    "CI/CD GitLab Jenkins Pipeline",
    "Monitoring Prometheus Grafana Observabilité",
    "Oracle DBA SQL Administration",
    "Ansible Terraform Infrastructure as Code",
    "DevSecOps Sécurité Applicative",
    "Consultant IT Infrastructure",
    "Administrateur Systèmes Unix",
    "AWS Azure Cloud Engineer",
]


def _get_access_token(client_id: str, client_secret: str) -> str:
    """Récupère un token OAuth2 France Travail (grant type client_credentials)."""
    try:
        resp = requests.post(
            FT_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": FT_SCOPE,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except ProxyError as e:
        logger.error("ProxyError while fetching FT token: %s", e)
        raise
    except RequestException as e:
        logger.error("RequestException while fetching FT token: %s", e)
        raise

    try:
        return resp.json()["access_token"]
    except ValueError:
        logger.error("Invalid JSON when fetching FT token (status=%s). Response text: %s",
                     resp.status_code, resp.text[:400])
        raise


def _normalize_offer(o: dict) -> dict:
    """Normalise une offre brute de l'API France Travail pour simplifier le rendu."""
    entreprise = o.get("entreprise") or {}
    lieu       = o.get("lieuTravail") or {}
    origine    = o.get("origineOffre") or {}
    salaire    = o.get("salaire") or {}
    # Normalize with defensive fallbacks for common API variations.
    # Some providers may use different keys for id/url — prefer canonical keys but
    # fall back to variants when present.
    offer_id = o.get('id') or o.get('offreId') or o.get('identifiant') or ''
    # origin object may contain several possible URL fields depending on provider
    origin_url = ''
    if isinstance(origine, dict):
        origin_url = origine.get('urlOrigine') or origine.get('url') or origine.get('lien') or origine.get('urlPublication') or ''
    # also check top-level url fields
    if not origin_url:
        origin_url = o.get('url') or o.get('lien') or o.get('urlOffre') or ''

    return {
        "id":                  offer_id,
        "intitule":            o.get("intitule", ""),
        "description":         o.get("description", ""),
        "dateCreation":        (o.get("dateCreation") or "")[:10],
        "typeContrat":         o.get("typeContrat", ""),
        "typeContratLibelle":  o.get("typeContratLibelle", ""),
        "modeTravail":         o.get("modesTravailLibelle", ""),
        "entreprise":          entreprise.get("nom", ""),
        "entrepriseAdaptee":   bool(entreprise.get("entrepriseAdaptee", False)),
        "lieu":                lieu.get("libelle", ""),
        "salaire":             salaire.get("libelle", ""),
        "url":                 origin_url,
        "experienceLibelle":   o.get("experienceLibelle", ""),
        "qualites": [
            q.get("libelle", "")
            for q in (o.get("qualitesProfessionnelles") or [])
        ],
        "competences": [
            c.get("libelle", "")
            for c in (o.get("competences") or [])
            if isinstance(c, dict) and c.get("libelle")
        ],
    }


def search_offers(
    client_id: str,
    client_secret: str,
    mots_cles: Optional[str] = None,
    types_contrat: Optional[list[str]] = None,
    departement: Optional[str] = None,
    mode_travail: Optional[str] = None,
    entreprises_adaptees: bool = False,
    min_creation_date: Optional[datetime] = None,
    max_results: int = 150,
) -> list[dict]:
    """
    Recherche d'offres d'emploi via l'API France Travail.

    :param client_id: Client ID de l'application francetravail.io
    :param client_secret: Client secret de l'application francetravail.io
    :param mots_cles: Mots-clés (espace = ET logique, ex: "Python DevOps Linux")
    :param types_contrat: Liste de codes contrat ["CDI", "CDD", …]
    :param departement: Code département ("06", "75", …) ou None = toute France
    :param mode_travail: Libellé mode travail ("Présentiel"/"Hybride"/"Télétravail") ou None
    :param entreprises_adaptees: True = employeurs handi-engagés uniquement
    :param min_creation_date: Filtre nouvelles offres (offres créées depuis cette date)
    :param max_results: Nombre max de résultats (≤ 150 par appel API)
    :return: Liste de dicts offres normalisés
    """
    token = _get_access_token(client_id, client_secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    params: dict[str, str] = {
        "sort":  "1",                               # tri par date de création décroissant
        "range": f"0-{min(max_results - 1, 149)}",  # max 150 offres par requête API
    }
    if mots_cles:
        params["motsCles"] = mots_cles
    # L'API FT v2 accepte au maximum 3 codes typeContrat ; au-delà → 400.
    # Si l'utilisateur a sélectionné plus de 3 types (ou tous), on omet le paramètre
    # pour obtenir tous les types (comportement par défaut de l'API).
    if types_contrat and len(types_contrat) <= 3:
        params["typeContrat"] = ",".join(types_contrat)
    if departement:
        params["departement"] = departement
    if mode_travail:
        params["modesTravailLibelle"] = mode_travail
    if entreprises_adaptees:
        params["entreprisesAdaptees"] = "true"
    if min_creation_date:
        params["minCreationDate"] = min_creation_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    url = f"{FT_API_BASE}/offres/search"
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    # 204 = aucun résultat, 200/206 = résultats (complets / partiels)
    if resp.status_code == 204:
        return []
    if resp.status_code not in (200, 206):
        resp.raise_for_status()

    raw_offers = resp.json().get("resultats", [])
    return [_normalize_offer(o) for o in raw_offers]


def search_auto_from_cv(
    client_id: str,
    client_secret: str,
    cv_data: dict,
    departement: Optional[str] = None,
    min_creation_date: Optional[datetime] = None,
    max_results: int = 150,
    extra_keywords: Optional[list[str]] = None,
) -> list[dict]:
    """
    Recherche automatique d'offres à partir du profil CV JSON Resume.

    Effectue plusieurs requêtes parallèles avec les mots-clés ATS déduits
    du profil, déduplique et retourne les offres les plus récentes.

    :param cv_data: Données cv.json (format JSON Resume)
    :param departement: Code département ("06", …) ou None = toute France
    :param min_creation_date: Récupérer seulement les offres créées depuis cette date
    :param max_results: Nombre max total d'offres retournées
    :return: Liste dédupliquée d'offres normalisées, triées par date de création (desc)
    """
    # Construire la liste de requêtes à partir du profil ATS + titre du CV
    # Tokenisation automatique : découpe le label et les compétences en tokens
    # courts pertinents (mots simples, bigrams), et priorise les langues/"Traducteur"/"Interprète".
    def tokenize_text(text: str) -> list[str]:
        if not text:
            return []
        import re
        # Remplacer séparateurs fréquents par espace
        t = re.sub(r'[\|/,_\-\\(\)\[\]<>]', ' ', text)
        # Séparer par espaces et filtrer tokens courts
        parts = [p.strip() for p in t.split() if p.strip()]
        tokens = []
        for p in parts:
            # garder mots composés jusqu'à 3 mots pour bigrams/trigrams
            tokens.append(p)
        # ajouter bigrams
        for i in range(len(parts) - 1):
            tokens.append(parts[i] + ' ' + parts[i+1])
        return tokens

    label = cv_data.get("basics", {}).get("label", "")
    low_label = (label or '').lower()
    is_translator = any(w in low_label for w in ['traduct', 'translate', 'interpret', 'interpr'])

    stopwords = {'pour', 'avec', 'dans', 'sur', 'les', 'des', 'une', 'par', 'qui', 'que', 'son', 'ses', 'aux', 'd', 'l', 'un', 'le', 'la', 'en', 'et', 'du', 'de', 'r&d', 'information', 'specialist', 'specialiste'}

    queries: list[str] = []
    seen: set[str] = set()

    def add_query(raw: str):
        if not raw:
            return
        # Clean special characters
        cleaned = re.sub(r'[\(\)\[\]<>]', ' ', raw).strip()
        # Remove noisy single stopwords
        words = [w.strip() for w in cleaned.split() if w.strip() and w.lower() not in stopwords]
        q_str = ' '.join(words)
        if not q_str or len(q_str) < 3 or q_str.lower() in stopwords:
            return
        # Avoid standalone languages unless candidate is a translator/interpreter
        if q_str.lower() in ('français', 'francais', 'anglais', 'japonais', 'espagnol', 'allemand', 'italien') and not is_translator:
            return
        if q_str.lower() not in seen:
            queries.append(q_str)
            seen.add(q_str.lower())

    # Priorité 1 : Mots-clés ATS sélectionnés par l'utilisateur ou suggérés par Gemini
    if extra_keywords:
        for ek in extra_keywords:
            if not ek:
                continue
            # Découper les intitulés composites très longs contenant / ou -
            subparts = re.split(r'[/&]|\s+-\s+', str(ek))
            for sp in subparts:
                add_query(sp)

    # Priorité 2 : Si pas d'extra_keywords ou pour compléter, extraire du label et des compétences du profil
    if len(queries) < 12:
        if label:
            for sp in re.split(r'[/&]|\s+-\s+', label):
                add_query(sp)
        for s in (cv_data.get('skills', []) or [])[:10]:
            name = s.get('name') if isinstance(s, dict) else str(s)
            if name:
                for sp in re.split(r'[/&]|\s+-\s+', name):
                    add_query(sp)
            if len(queries) >= 15:
                break

    # Priorité 3 : Postes occupés dans le CV
    if len(queries) < 10:
        for w in (cv_data.get('work', []) or [])[:5]:
            pos = (w.get('position') or '').strip()
            if pos:
                for sp in re.split(r'[/&]|\s+-\s+', pos):
                    add_query(sp)
            if len(queries) >= 15:
                break

    # Traducteur / Interprète spécifique
    if is_translator:
        for lang in ('Français', 'Anglais', 'Japonais', 'Espagnol', 'Allemand', 'Italien'):
            if lang.lower() in low_label:
                add_query(lang + ' bilingue')
                add_query(lang)

    # Tronquer pour ne pas surcharger l'API FT
    queries = queries[:15]

    all_offers: dict[str, dict] = {}

    for q in queries:
        try:
            offers = search_offers(
                client_id=client_id,
                client_secret=client_secret,
                mots_cles=q,
                departement=departement,
                min_creation_date=min_creation_date,
                max_results=50,
            )
            for o in offers:
                oid = o.get("id", "")
                if oid and oid not in all_offers:
                    all_offers[oid] = o
        except Exception as exc:
            logger.warning("FT auto-search '%s' failed: %s", q, exc)

    # Tri par dateCreation décroissant
    offers_list = sorted(
        all_offers.values(),
        key=lambda o: o.get("dateCreation", ""),
        reverse=True,
    )
    return offers_list[:max_results]


# ── Intégration Gemini & Matching Candidat ─────────────────────────────────────

def generate_keywords_with_gemini(cv_data: dict, api_key: str | None = None,
                                  model: str | None = None,
                                  base_url: str | None = None) -> list[str]:
    """Génère avec Gemini une liste de mots-clés optimisés pour l'API France Travail."""
    try:
        from config import Config
        api_key = api_key or getattr(Config, 'GITHUB_TOKEN', '')
        model = model or getattr(Config, 'GITHUB_MODELS_MODEL', 'gemini-3.5-flash-lite')
        base_url = base_url or getattr(Config, 'GITHUB_MODELS_BASE_URL', 'https://generativelanguage.googleapis.com')
    except Exception:
        pass

    fallback_keywords = [
        "Administrateur Linux",
        "Ingénieur Système",
        "Développeur Python",
        "Ingénieur DevOps",
        "Supervision Linux",
        "Support N3",
        "Intégrateur Technique",
        "Test logiciel ISTQB",
        "Cybersécurité",
        "Administrateur Unix",
        "Développeur C++",
        "Développeur Delphi",
    ]

    if not api_key or api_key == 'ollama-local':
        return fallback_keywords

    try:
        from tools.github_models_client import chat_completion
        import json as _json

        label = cv_data.get('basics', {}).get('label', '')
        skills = [s['name'] for s in cv_data.get('skills', []) if isinstance(s, dict) and s.get('name')]
        roles = [w.get('position') for w in cv_data.get('work', [])[:4] if isinstance(w, dict) and w.get('position')]
        certs = [c.get('name') for c in cv_data.get('certificates', []) if isinstance(c, dict) and c.get('name')]

        prompt = (
            "Tu es un expert RH et du moteur de recherche de France Travail.\n"
            "Profil du candidat :\n"
            f"- Métier : {label}\n"
            f"- Compétences : {', '.join(skills)}\n"
            f"- Postes récents : {', '.join(roles)}\n"
            f"- Certifications : {', '.join(certs)}\n\n"
            "Génère entre 8 et 12 mots-clés ou intitulés de recherche courts (1 à 3 mots maximum par élément) "
            "les plus efficaces pour interroger l'API France Travail afin de remonter des offres d'emploi IT "
            "hautement pertinentes (ex: Administrateur Linux, Développeur Python, Ingénieur Système, etc.).\n"
            "Réponds uniquement par un JSON valide avec cette structure :\n"
            '{"keywords": ["mot_cle_1", "mot_cle_2", ...]}'
        )

        resp = chat_completion(
            messages=[{'role': 'user', 'content': prompt}],
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0.3,
            max_tokens=300,
            response_format={'type': 'json_object'}
        )
        if resp:
            data = _json.loads(resp)
            kws = data.get('keywords', [])
            if isinstance(kws, list) and kws:
                cleaned = [str(k).strip() for k in kws if str(k).strip()]
                if cleaned:
                    return cleaned
    except Exception as exc:
        logger.warning(f"generate_keywords_with_gemini failed: {exc}")

    return fallback_keywords


def compute_offer_matching(offer: dict, cv_data: dict) -> dict:
    """Calcule le pourcentage d'adéquation (0-100%) entre une offre et le profil CV.
    
    Structure dynamique inspirée de LinkedIn :
    - Adapté au profil réel du candidat (skills, titre cible, domaine d'activité)
    - Détection des compétences correspondantes (matched_skills)
    - Évaluation du titre du poste par rapport au domaine d'expertise
    - Score global en pourcentage
    """
    import re

    intitule = (offer.get('intitule') or '').strip()
    description = (offer.get('description') or '').strip()
    full_text = f"{intitule} {description}".lower()
    title_lower = intitule.lower()

    # 1. Données du profil candidat
    basics = cv_data.get('basics', {}) or {}
    label = (basics.get('label') or '').strip()
    summary = (basics.get('summary') or '').strip()

    # Liste des compétences du candidat
    profile_skills = []
    for s in (cv_data.get('skills', []) or []):
        name = s.get('name') if isinstance(s, dict) else str(s)
        if name and name.strip():
            profile_skills.append(name.strip())
            if isinstance(s, dict):
                for kw in s.get('keywords', []) or []:
                    if kw and kw.strip():
                        profile_skills.append(kw.strip())

    # Expériences et intitulés de postes passés
    work_titles = []
    for w in (cv_data.get('work', []) or []):
        pos = (w.get('position') or '').strip()
        if pos:
            work_titles.append(pos)

    # 2. Construction du vocabulaire de domaine du candidat
    stopwords = {
        'pour', 'avec', 'dans', 'sur', 'les', 'des', 'une', 'par', 'qui', 'que',
        'son', 'ses', 'aux', 'un', 'le', 'la', 'en', 'et', 'du', 'de', 'd', 'l',
        'r&d', 'information', 'specialist', 'specialiste'
    }
    # Rôles génériques transversaux à tous les secteurs (non distinctifs à eux seuls)
    generic_role_nouns = {
        'ingénieur', 'ingenieur', 'technicien', 'responsable', 'chef', 'directeur',
        'chargé', 'charge', 'assistant', 'stagiaire', 'opérateur', 'operateur',
        'cadre', 'analyste', 'expert', 'consultant', 'manager', 'lead', 'coordinateur',
        'projet', 'projets', 'project', 'projects', 'pilote', 'mission', 'missions',
        'gestionnaire', 'collaborateur', 'collaboratrice', 'agent'
    }

    def clean_tokens(text: str) -> list[str]:
        cleaned = re.sub(r'[\|/,_\-\\(\)\[\]<>:;\"\'’]', ' ', text.lower())
        return [w.strip() for w in cleaned.split() if len(w.strip()) >= 3 and w.strip() not in stopwords]

    candidate_domain_tokens = set()
    candidate_domain_phrases = set()

    for src in [label] + work_titles + profile_skills:
        words = clean_tokens(src)
        for w in words:
            if w not in generic_role_nouns:
                candidate_domain_tokens.add(w)
        for i in range(len(words) - 1):
            candidate_domain_phrases.add(words[i] + ' ' + words[i+1])

    # 3. Correspondance des compétences
    generic_single_words = {
        'qualité', 'qualite', 'gestion', 'management', 'analyse', 'analyses',
        'recherche', 'recherches', 'développement', 'developpement', 'support',
        'conseil', 'projet', 'projets', 'service', 'services', 'système', 'systeme'
    }

    matched_skills = []
    for sk in profile_skills:
        sk_clean = sk.lower().strip()
        # Test mot entier
        sk_pattern = r'\b' + re.escape(sk_clean) + r'\b'
        if re.search(sk_pattern, full_text):
            if sk not in matched_skills:
                matched_skills.append(sk)
        else:
            # Test sous-termes significatifs (ex: 'Contrôle qualité' dans 'Qualité - Contrôle qualité')
            parts = [p.strip() for p in re.split(r'[-/]', sk_clean) if len(p.strip()) >= 4]
            for p in parts:
                p_words = p.split()
                # Ignorer les mots seuls trop génériques dans les descriptions d'entreprises
                if len(p_words) == 1 and p_words[0] in generic_single_words:
                    continue
                if re.search(r'\b' + re.escape(p) + r'\b', full_text):
                    if sk not in matched_skills:
                        matched_skills.append(sk)
                    break

    # 4. Évaluation Titre / Métier (45% du score)
    title_words = set(clean_tokens(title_lower))
    # Tokens de domaine spécifiques présents dans le titre
    matched_domain_tokens = title_words.intersection(candidate_domain_tokens)
    matched_domain_phrases = [ph for ph in candidate_domain_phrases if ph in title_lower]

    if matched_domain_phrases or len(matched_domain_tokens) >= 2:
        title_score = 92
    elif len(matched_domain_tokens) == 1:
        title_score = 75
    elif matched_skills:
        title_score = 45
    else:
        title_score = 10

    # Si le titre n'a aucun lien avec le domaine du candidat et aucune compétence ne correspond : HORS PROFIL
    if title_score <= 15 and not matched_skills:
        return {
            'score': 10,
            'level': 'low',
            'matched_skills': [],
            'missing_skills': [],
            'summary': f"Hors profil : intitulé et secteur sans lien avec votre parcours ({label[:35]}...).",
            'details': {'title_score': 10, 'skills_score': 0, 'exp_score': 0, 'geo_score': 0}
        }

    # 5. Évaluation Compétences (40% du score)
    if matched_skills:
        skills_score = min(96, 45 + len(matched_skills) * 12)
    elif matched_domain_tokens:
        skills_score = 40
    else:
        skills_score = 20

    # 6. Évaluation Séniorité & Expérience (10% du score)
    exp_text = (offer.get('experienceLibelle') or '').lower()
    years = basics.get('yearsOfExperience') or (len(work_titles) * 3) or 10
    is_senior_profile = years >= 6
    if any(k in full_text or k in exp_text for k in ['senior', 'sénior', 'confirmé', 'confirme', 'expert', '5 an', '10 an']):
        exp_score = 95 if is_senior_profile else 55
    elif any(k in full_text or k in exp_text for k in ['débutant', 'debutant', 'junior', 'alternant', 'stage']):
        exp_score = 65 if is_senior_profile else 90
    else:
        exp_score = 80

    # 7. Évaluation Géographie & Mobilité (5% du score)
    lieu_lower = (offer.get('lieu') or '').lower()
    cand_city = (basics.get('location', {}).get('city') or '').lower()
    if cand_city and cand_city in lieu_lower:
        geo_score = 95
    elif any(loc in lieu_lower for loc in ['06', 'nice', 'sophia', 'mougins', 'antibes', 'cannes', 'grasse', 'biot', 'valbonne', 'saint-laurent']):
        geo_score = 90
    elif any(loc in lieu_lower for loc in ['83', '13', 'marseille', 'aix', 'toulon', 'paca']):
        geo_score = 80
    elif 'télétravail' in full_text or 'teletravail' in full_text:
        geo_score = 90
    else:
        geo_score = 65

    raw_score = round(title_score * 0.45 + skills_score * 0.40 + exp_score * 0.10 + geo_score * 0.05)
    final_score = max(10, min(97, raw_score))

    if final_score >= 70:
        level = 'high'
        summary = f"Forte adéquation avec vos compétences ({', '.join(matched_skills[:3]) or label[:30]})."
    elif final_score >= 45:
        level = 'medium'
        summary = f"Adéquation modérée ({', '.join(matched_skills[:2]) or 'compétences transversales'})."
    else:
        level = 'low'
        summary = f"Faible adéquation : intitulé ou secteur éloigné de votre spécialité ({label[:35]}...)."

    return {
        'score': final_score,
        'level': level,
        'matched_skills': matched_skills,
        'missing_skills': [],
        'summary': summary,
        'details': {
            'title_score': title_score,
            'skills_score': skills_score,
            'exp_score': exp_score,
            'geo_score': geo_score,
        }
    }


def enrich_offers_with_matching(offers: list[dict], cv_data: dict, sort_by_score: bool = True) -> list[dict]:
    """Enrichit chaque offre avec son pourcentage de matching et trie par pertinence."""
    enriched = []
    for o in offers:
        m = compute_offer_matching(o, cv_data)
        o_copy = dict(o)
        o_copy['match_score'] = m['score']
        o_copy['matching'] = m
        enriched.append(o_copy)

    if sort_by_score:
        enriched.sort(key=lambda x: (x.get('match_score', 0), x.get('dateCreation', '')), reverse=True)

    return enriched


def evaluate_offer_with_gemini(offer: dict, cv_data: dict, api_key: str | None = None) -> dict:
    """Analyse approfondie de l'adéquation d'une offre via Gemini (style recruteur LinkedIn)."""
    try:
        from config import Config
        api_key = api_key or getattr(Config, 'GITHUB_TOKEN', '')
        model = getattr(Config, 'GITHUB_MODELS_MODEL', 'gemini-3.5-flash-lite')
        base_url = getattr(Config, 'GITHUB_MODELS_BASE_URL', 'https://generativelanguage.googleapis.com')
        from tools.github_models_client import chat_completion
        import json as _json

        basics = cv_data.get('basics', {}) or {}
        label = basics.get('label', '')
        summary = basics.get('summary', '')
        skills_str = ', '.join([
            (s.get('name') if isinstance(s, dict) else str(s))
            for s in (cv_data.get('skills', []) or [])
        ])
        works = []
        for w in (cv_data.get('work', []) or [])[:3]:
            pos = w.get('position', '')
            comp = w.get('company', '') or w.get('name', '')
            if pos:
                works.append(f"{pos} ({comp})" if comp else pos)
        works_str = '; '.join(works) if works else "Non renseigné"

        certs = []
        for c in (cv_data.get('certificates', []) or []):
            c_name = c.get('name') if isinstance(c, dict) else str(c)
            if c_name:
                certs.append(c_name)
        certs_str = ', '.join(certs) if certs else "Non renseigné"

        prompt = (
            "Tu es un recruteur expert en ressources humaines. Analyse avec objectivité l'adéquation entre cette offre d'emploi et le profil réel du candidat.\n\n"
            f"OFFRE D'EMPLOI :\n"
            f"- Intitulé : {offer.get('intitule')}\n"
            f"- Entreprise : {offer.get('entreprise')}\n"
            f"- Lieu : {offer.get('lieu')}\n"
            f"- Contrat : {offer.get('typeContratLibelle')}\n"
            f"- Description : {offer.get('description', '')[:1200]}\n\n"
            f"PROFIL DU CANDIDAT :\n"
            f"- Titre / Métier ciblé : {label}\n"
            f"- Synthèse : {summary[:300]}\n"
            f"- Compétences clés : {skills_str}\n"
            f"- Expériences marquantes : {works_str}\n"
            f"- Formations & Certifications : {certs_str}\n\n"
            "Consigne impérative :\n"
            "Si l'offre appartient à un secteur ou un métier complètement différent du profil du candidat (par exemple une offre informatique pour un profil pharmacie/chimie, ou inversement), attribue un score très bas (10 à 20) et indique clairement le décalage de secteur dans le verdict.\n"
            "Retourne uniquement un JSON avec :\n"
            "{\n"
            '  "score": (entier entre 10 et 98),\n'
            '  "strengths": [liste de 2 à 4 points forts majeurs de correspondance ou éléments transversaux],\n'
            '  "missing_or_to_develop": [liste de 1 à 3 compétences indispensables manquantes],\n'
            '  "verdict": "synthèse en 2 phrases du recruteur sur la pertinence et les chances réelles"\n'
            "}"
        )

        resp = chat_completion(
            messages=[{'role': 'user', 'content': prompt}],
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0.2,
            max_tokens=400,
            response_format={'type': 'json_object'}
        )
        if resp:
            data = _json.loads(resp)
            return data
    except Exception as exc:
        logger.warning(f"evaluate_offer_with_gemini failed: {exc}")

    # Fallback heuristique
    base_match = compute_offer_matching(offer, cv_data)
    return {
        "score": base_match["score"],
        "strengths": base_match["matched_skills"],
        "missing_or_to_develop": base_match.get("missing_skills", []),
        "verdict": base_match["summary"]
    }
