#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_offres_cv_philippe.py
Lecture en chunks d'un CSV d'offres, scoring par mots-clés orientés IT et export top20.
Usage: python match_offres_cv_philippe.py
"""

import csv
import os
import re
from datetime import datetime

import pandas as pd
from dateutil import parser as dateparser
from rapidfuzz import fuzz
from tqdm import tqdm

# ---------------------------
# Configuration utilisateur
# ---------------------------
INPUT_CSV = "offres_france_travail__06_.csv"
OUTPUT_CSV = "top20_offres_matching_Philippe_MOUREY.csv"
CHUNK_SIZE = 20000
MAX_RESULTS = 20

# Colonnes attendues (adapter si noms différents)
CANDIDATE_COLUMNS = {
    "title": ["intitulé", "intitule", "titre", "poste", "intitulé du poste"],
    "employer": ["employeur", "organisme", "structure", "entreprise"],
    "location": ["localisation", "ville", "lieu", "adresse"],
    "contract": ["type_contrat", "contrat", "type de contrat"],
    "description": ["description", "offre", "missions", "profil", "texte"],
    "diploma": ["diplome", "diplôme", "niveau_requis", "formation"],
    "link": ["lien", "url", "offre_url"],
    "date": ["date", "date_publication", "date_de_publication"]
}

# Mots-clés et pondérations orientés IT
KEYWORDS = {
    # Langages & scripting
    "python": 12, "bash": 8, "shell scripting": 8, "sql": 10, "delphi": 8,
    # Infrastructure & OS
    "linux": 12, "unix": 10, "rhel": 8, "debian": 8, "ubuntu": 8,
    # Conteneurisation & orchestration
    "docker": 10, "kubernetes": 12, "helm": 8, "podman": 6,
    # DevOps & CI/CD
    "devops": 14, "devsecops": 14, "ci/cd": 12, "gitlab ci": 10, "jenkins": 8,
    "pipeline": 8, "gitops": 8,
    # Cloud
    "aws": 10, "azure": 10, "gcp": 8, "cloud": 10, "infrastructure as code": 10,
    "terraform": 10, "ansible": 10, "chef": 6, "puppet": 6,
    # Site Reliability
    "sre": 12, "site reliability": 12, "observabilité": 8,
    # Monitoring & alerting
    "monitoring": 10, "prometheus": 8, "grafana": 8, "datadog": 8,
    "nagios": 6, "zabbix": 6, "tivoli": 8, "splunk": 8,
    # Cybersécurité
    "cybersécurité": 14, "cybersecurity": 14, "sécurité": 12, "security": 12,
    "ethical hacking": 15, "pentest": 14, "penetration testing": 14,
    "audit de sécurité": 14, "iso 27001": 12, "iso 27005": 12,
    "siem": 10, "soc": 10, "vulnerability management": 10,
    # Tests
    "istqb": 8, "testeur": 8, "qa": 8, "test automation": 8,
    # Bases de données
    "oracle": 10, "postgresql": 8, "mysql": 8,
    # Architecture & intégration
    "intégration": 10, "integration": 10, "microservices": 10,
    "api rest": 10, "architecture": 10, "middleware": 8,
    # Titres de postes (ATS critical)
    "ingénieur devops": 14, "ingénieur systèmes": 12, "ingénieur sécurité": 14,
    "consultant it": 10, "architecte si": 12, "développeur": 10,
    "intégrateur": 10, "administrateur systèmes": 10, "administrateur linux": 10,
    # Entreprises connues
    "sopra steria": 6, "capgemini": 5, "thales": 6, "atos": 5,
    # Divers
    "tma": 8, "infogérance": 8, "agilité": 6, "scrum": 6, "kanban": 6,
}

# Localisations prioritaires
PRIORITY_LOCATIONS = [
    "saint-laurent-du-var", "saint laurent du var", "nice", "cagnes", "cagnes-sur-mer",
    "alpes-maritimes", "paca", "06", "sophia antipolis"
]

# Pondérations globales
WEIGHTS = {
    "keywords": 0.65,
    "title": 0.15,
    "location": 0.10,
    "diploma": 0.10
}

# ---------------------------
# Fonctions utilitaires
# ---------------------------
def normalize_text(s):
    if pd.isna(s):
        return ""
    s = str(s).lower()
    s = s.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("ô", "o").replace("ç", "c")
    s = re.sub(r"[^a-z0-9\s\-\/\+]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def detect_column(df_cols, candidates):
    for c in candidates:
        for col in df_cols:
            if normalize_text(col) == normalize_text(c):
                return col
    for c in candidates:
        best = None
        best_score = 0
        for col in df_cols:
            score = fuzz.partial_ratio(normalize_text(col), normalize_text(c))
            if score > best_score:
                best_score = score
                best = col
        if best_score > 85:
            return best
    return None

def extract_columns(df):
    cols = {}
    df_cols = list(df.columns)
    for key, candidates in CANDIDATE_COLUMNS.items():
        found = detect_column(df_cols, candidates)
        cols[key] = found
    return cols

def keyword_score(text):
    text_n = normalize_text(text)
    score = 0
    matched = []
    for kw, weight in KEYWORDS.items():
        if kw in text_n:
            score += weight
            matched.append(kw)
        else:
            if len(kw.split()) > 1:
                ratio = fuzz.partial_ratio(kw, text_n)
                if ratio > 85:
                    score += weight * 0.9
                    matched.append(kw + " (fuzzy)")
    return score, matched

def title_bonus(title):
    if not title:
        return 0
    t = normalize_text(title)
    bonuses = 0
    for term in ["ingénieur", "ingenieur", "consultant", "developpeur", "développeur", "devops", "sre", "architecte", "intégrateur", "testeur"]:
        if term in t:
            bonuses += 12
    return bonuses

def location_bonus(location):
    if not location:
        return 0
    loc = normalize_text(location)
    for p in PRIORITY_LOCATIONS:
        if p in loc:
            return 15
    for p in PRIORITY_LOCATIONS:
        if fuzz.partial_ratio(p, loc) > 85:
            return 10
    return 0

def diploma_bonus(diploma_text):
    if not diploma_text:
        return 0
    d = normalize_text(diploma_text)
    bonus = 0
    if "istqb" in d or "testeur" in d:
        bonus += 8
    if "master" in d or "maitrise" in d or "maîtrise" in d:
        bonus += 8
    if "gcih" in d or "giac" in d or "iso" in d:
        bonus += 10
    return bonus

def compute_score(row_texts):
    kw_score, matched = keyword_score(row_texts.get("description", "") + " " + row_texts.get("title", ""))
    kw_norm = min(kw_score, 100)
    t_bonus = title_bonus(row_texts.get("title", ""))
    loc_bonus = location_bonus(row_texts.get("location", ""))
    dip_bonus = diploma_bonus(row_texts.get("diploma", ""))
    raw = (WEIGHTS["keywords"] * kw_norm) + (WEIGHTS["title"] * t_bonus * 2) + (WEIGHTS["location"] * loc_bonus * 2) + (WEIGHTS["diploma"] * dip_bonus * 2)
    score = max(0, min(100, int(round(raw))))
    return score, matched

# ---------------------------
# Traitement principal
# ---------------------------
def process_file(input_csv, chunk_size=CHUNK_SIZE):
    results = []
    total_rows = 0
    encodings = ["utf-8", "latin-1", "cp1252"]
    sep_candidates = [",", ";", "\t", "|"]
    df_sample = None
    for enc in encodings:
        for sep in sep_candidates:
            try:
                df_sample = pd.read_csv(input_csv, nrows=5, encoding=enc, sep=sep)
                encoding_used = enc
                sep_used = sep
                break
            except Exception:
                df_sample = None
        if df_sample is not None:
            break
    if df_sample is None:
        raise RuntimeError("Impossible de détecter l'encodage ou le séparateur du CSV. Exporter en UTF-8 et séparateur ','.")

    reader = pd.read_csv(input_csv, encoding=encoding_used, sep=sep_used, chunksize=chunk_size, dtype=str, low_memory=True)
    first = True
    for chunk in tqdm(reader, desc="Lecture CSV"):
        total_rows += len(chunk)
        if first:
            cols_map = extract_columns(chunk)
            first = False
        def safe_get(colname, df=chunk):
            if colname and colname in df.columns:
                return df[colname].astype(str).fillna("")
            return pd.Series([""] * len(df))
        titles = safe_get(cols_map.get("title"))
        employers = safe_get(cols_map.get("employer"))
        locations = safe_get(cols_map.get("location"))
        contracts = safe_get(cols_map.get("contract"))
        descriptions = safe_get(cols_map.get("description"))
        diplomas = safe_get(cols_map.get("diploma"))
        links = safe_get(cols_map.get("link"))
        dates = safe_get(cols_map.get("date"))

        for idx in range(len(chunk)):
            row_texts = {
                "title": titles.iloc[idx],
                "description": descriptions.iloc[idx],
                "location": locations.iloc[idx],
                "diploma": diplomas.iloc[idx]
            }
            score, matched = compute_score(row_texts)
            res = {
                "Intitulé du poste": titles.iloc[idx].strip(),
                "Employeur": employers.iloc[idx].strip(),
                "Localisation": locations.iloc[idx].strip(),
                "Type de contrat": contracts.iloc[idx].strip(),
                "Score": score,
                "Critères matchés": "; ".join(matched) if matched else "",
                "LienOffre": links.iloc[idx].strip(),
                "DatePublication": ""
            }
            date_raw = dates.iloc[idx].strip()
            if date_raw:
                try:
                    dt = dateparser.parse(date_raw, dayfirst=True, fuzzy=True)
                    res["DatePublication"] = dt.strftime("%Y-%m-%d")
                except Exception:
                    res["DatePublication"] = date_raw
            results.append(res)

    df_res = pd.DataFrame(results)
    if df_res.empty:
        raise RuntimeError("Aucune offre exploitables trouvée dans le fichier.")
    df_res = df_res.sort_values(by="Score", ascending=False).reset_index(drop=True)
    top_df = df_res.head(MAX_RESULTS).copy()
    for col in top_df.columns:
        top_df[col] = top_df[col].astype(str).apply(lambda x: " ".join(x.splitlines()).strip())
    top_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    return top_df, total_rows

if __name__ == "__main__":
    print("Démarrage du matching offres -> CV (Philippe MOUREY)")
    if not os.path.exists(INPUT_CSV):
        print(f"Fichier introuvable: {INPUT_CSV}")
        raise SystemExit(1)
    try:
        top_df, total = process_file(INPUT_CSV)
        print(f"Traitement terminé. {total} lignes analysées.")
        print(f"Top {len(top_df)} exportées dans: {OUTPUT_CSV}")
        print(top_df[["Intitulé du poste", "Employeur", "Localisation", "Type de contrat", "Score", "Critères matchés"]].to_string(index=False))
    except Exception as e:
        print("Erreur lors du traitement:", str(e))
        raise
