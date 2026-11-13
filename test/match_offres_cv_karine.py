#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
match_offres_cv.py
Lecture en chunks d'un CSV d'offres, scoring par mots-clés et export top20.
Usage: python match_offres_cv.py
"""

import os
import re
import csv
import math
from datetime import datetime
from dateutil import parser as dateparser
from rapidfuzz import fuzz
import pandas as pd
from tqdm import tqdm

# ---------------------------
# Configuration utilisateur
# ---------------------------
INPUT_CSV = "offres_france_travail__06_.csv"   # chemin vers le CSV local
OUTPUT_CSV = "top20_offres_matching_Karine_MALARD.csv"
CHUNK_SIZE = 20000                             # ajuster selon RAM
MAX_RESULTS = 20

# Colonnes attendues (adapter si noms différents)
CANDIDATE_COLUMNS = {
    "title": ["intitulé", "intitule", "titre", "poste", "intitulé du poste", "intitule_du_poste"],
    "employer": ["employeur", "organisme", "structure", "entreprise"],
    "location": ["localisation", "ville", "lieu", "adresse"],
    "contract": ["type_contrat", "contrat", "type de contrat"],
    "description": ["description", "offre", "missions", "profil", "texte"],
    "diploma": ["diplome", "diplôme", "niveau_requis", "formation"],
    "link": ["lien", "url", "offre_url"],
    "date": ["date", "date_publication", "date_de_publication"]
}

# Mots-clés et pondérations (modifiable)
KEYWORDS = {
    # mots-clés exacts -> poids
    "gestion": 10,
    "gestion administrative": 12,
    "gestion budgétaire": 12,
    "budget": 8,
    "encadrement": 12,
    "manager": 10,
    "management": 10,
    "cadre": 10,
    "responsable": 12,
    "directeur": 12,
    "adjoint": 8,
    "chef de projet": 12,
    "pilotage": 10,
    "projet": 8,
    "projets": 8,
    "meсs": 15,   # MECS (attention accents)
    "mecs": 15,
    "mas": 15,
    "fae": 15,
    "samsah": 12,
    "cafdes": 15,
    "master 2": 10,
    "droit de la sante": 12,
    "droit de la santé": 12,
    "troubles du comportement": 10,
    "soutien à la parentalité": 10,
    "ressources humaines": 8,
    "rh": 6,
    "pilotage de projet": 12,
    "rédaction": 6,
    "procédure": 8,
    "qualité": 6,
    "accompagnement personnalisé": 10
}

# Localisations prioritaires (bonus)
PRIORITY_LOCATIONS = [
    "nice", "cagnes", "cagnes-sur-mer", "saint-laurent-du-var", "saint laurent du var",
    "alpes-maritimes", "06", "paca", "provence-alpes-cote d'azur", "provence-alpes-côte d'azur"
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
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def detect_column(df_cols, candidates):
    for c in candidates:
        for col in df_cols:
            if normalize_text(col) == normalize_text(c):
                return col
    # fuzzy match fallback
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
            # fuzzy fallback for multi-word keywords
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
    for term in ["responsable", "cadre", "directeur", "adjoint", "chef", "manager"]:
        if term in t:
            bonuses += 10
    return bonuses

def location_bonus(location):
    if not location:
        return 0
    loc = normalize_text(location)
    for p in PRIORITY_LOCATIONS:
        if p in loc:
            return 15
    # fuzzy city match
    for p in PRIORITY_LOCATIONS:
        if fuzz.partial_ratio(p, loc) > 85:
            return 10
    return 0

def diploma_bonus(diploma_text):
    if not diploma_text:
        return 0
    d = normalize_text(diploma_text)
    bonus = 0
    if "cafdes" in d:
        bonus += 20
    if "master" in d or "master 2" in d:
        bonus += 10
    if "droit de la sante" in d or "droit de la sante" in d:
        bonus += 10
    return bonus

def compute_score(row_texts):
    # row_texts: dict with keys title, description, location, diploma
    kw_score, matched = keyword_score(row_texts.get("description", "") + " " + row_texts.get("title", ""))
    # normalize kw_score to 0-100 by a heuristic max
    kw_norm = min(kw_score, 100)
    t_bonus = title_bonus(row_texts.get("title", ""))
    loc_bonus = location_bonus(row_texts.get("location", ""))
    dip_bonus = diploma_bonus(row_texts.get("diploma", ""))
    # combine with weights
    raw = (WEIGHTS["keywords"] * kw_norm) + (WEIGHTS["title"] * t_bonus * 2) + (WEIGHTS["location"] * loc_bonus * 2) + (WEIGHTS["diploma"] * dip_bonus * 2)
    score = max(0, min(100, int(round(raw))))
    return score, matched

# ---------------------------
# Traitement principal
# ---------------------------
def process_file(input_csv, chunk_size=CHUNK_SIZE):
    results = []
    total_rows = 0
    # Try to infer encoding and separator by pandas; fallback to utf-8 and comma
    encodings = ["utf-8", "latin-1", "cp1252"]
    sep_candidates = [",", ";", "\t", "|"]
    df_sample = None
    for enc in encodings:
        for sep in sep_candidates:
            try:
                df_sample = pd.read_csv(input_csv, nrows=5, encoding=enc, sep=sep)
                # success
                encoding_used = enc
                sep_used = sep
                break
            except Exception:
                df_sample = None
        if df_sample is not None:
            break
    if df_sample is None:
        raise RuntimeError("Impossible de détecter l'encodage ou le séparateur du CSV. Essayez d'exporter en UTF-8 et séparateur ','.")

    # Read in chunks
    reader = pd.read_csv(input_csv, encoding=encoding_used, sep=sep_used, chunksize=chunk_size, dtype=str, low_memory=True)
    first = True
    for chunk in tqdm(reader, desc="Lecture CSV"):
        total_rows += len(chunk)
        if first:
            cols_map = extract_columns(chunk)
            first = False
        # Ensure columns exist in chunk
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
            # Build result row
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
            # try parse date
            date_raw = dates.iloc[idx].strip()
            if date_raw:
                try:
                    dt = dateparser.parse(date_raw, dayfirst=True, fuzzy=True)
                    res["DatePublication"] = dt.strftime("%Y-%m-%d")
                except Exception:
                    res["DatePublication"] = date_raw
            results.append(res)

    # Sort and keep top N
    df_res = pd.DataFrame(results)
    if df_res.empty:
        raise RuntimeError("Aucune offre exploitables trouvée dans le fichier.")
    df_res = df_res.sort_values(by="Score", ascending=False).reset_index(drop=True)
    top_df = df_res.head(MAX_RESULTS).copy()
    # Ensure single-line cells
    for col in top_df.columns:
        top_df[col] = top_df[col].astype(str).apply(lambda x: " ".join(x.splitlines()).strip())
    # Export CSV
    top_df.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_MINIMAL)
    return top_df, total_rows

# ---------------------------
# Exécution
# ---------------------------
if __name__ == "__main__":
    print("Démarrage du matching offres -> CV")
    if not os.path.exists(INPUT_CSV):
        print(f"Fichier introuvable: {INPUT_CSV}")
        raise SystemExit(1)
    try:
        top_df, total = process_file(INPUT_CSV)
        print(f"Traitement terminé. {total} lignes analysées.")
        print(f"Top {len(top_df)} exportées dans: {OUTPUT_CSV}")
        # Affichage sommaire
        print(top_df[["Intitulé du poste", "Employeur", "Localisation", "Type de contrat", "Score", "Critères matchés"]].to_string(index=False))
    except Exception as e:
        print("Erreur lors du traitement:", str(e))
        raise
