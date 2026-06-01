"""
Client API France Travail v2 pour la recherche d'offres d'emploi.

Authentification : OAuth2 client_credentials
Documentation : https://francetravail.io/produits-partages/catalogue/offres-emploi/documentation
Base URL : https://api.francetravail.io/partenaire/offresdemploi/v2
Token URL : https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire
"""
from __future__ import annotations

import logging
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
    return {
        "id":                  o.get("id", ""),
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
        "url":                 origine.get("urlOrigine", ""),
        "experienceLibelle":   o.get("experienceLibelle", ""),
        "qualites": [
            q.get("libelle", "")
            for q in (o.get("qualitesProfessionnelles") or [])
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
    label = cv_data.get("basics", {}).get("label", "")
    queries: list[str] = []
    if label:
        queries.append(label)
    # Ajouter les requêtes ATS prédéfinies (max 7 pour ne pas surcharger l'API)
    for kw in ATS_KEYWORDS_PROFILE:
        if kw not in queries:
            queries.append(kw)
        if len(queries) >= 7:
            break

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
