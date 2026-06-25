"""
Utilitaire simple pour fusionner plusieurs CV JSON exportés/importés.

Fonctionnalités:
- merge_cv_jsons(paths, selections) : lit plusieurs fichiers JSON et compose un CV
  en prenant, pour chaque section connue, la version choisie via `selections`.

Le format attendu est identique à celui produit par `parse_json_cv` / `load_cv_data`.
"""
from pathlib import Path
import json
from typing import Dict, List, Any

KNOWN_SECTIONS = [
    'basics', 'work', 'education', 'skills', 'projects', 'certificates', 'references', 'languages', 'volunteer'
]


def load_json(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding='utf-8')
    return json.loads(raw)


def merge_cv_jsons(paths: List[Path], selections: Dict[str, str]) -> Dict[str, Any]:
    """Merge multiple CV JSON files.

    - `paths` : liste de Path vers fichiers JSON
    - `selections` : mapping section -> filename indiquant quelle source utiliser pour la section

    Pour les sections non listées dans `selections`, on prend la première occurrence non vide
    trouvée parmi les fichiers dans l'ordre fourni.
    """
    sources = {p.name: load_json(p) for p in paths}

    merged: Dict[str, Any] = {}

    # first, copy basics from default selection or first source
    if 'basics' in selections and selections['basics'] in sources:
        merged['basics'] = sources[selections['basics']].get('basics', {})
    else:
        for s in sources.values():
            if s.get('basics'):
                merged['basics'] = s.get('basics')
                break
        else:
            merged['basics'] = {}

    for section in KNOWN_SECTIONS:
        if section == 'basics':
            continue
        chosen = None
        fname = selections.get(section)
        if fname and fname in sources:
            chosen = sources[fname].get(section)
        if chosen is None:
            # fallback: first non-empty
            for s in sources.values():
                val = s.get(section)
                if val:
                    chosen = val
                    break
        if chosen is not None:
            merged[section] = chosen

    # Merge any other keys present in sources (like metadata) - prefer first source
    for s in paths:
        data = sources.get(s.name, {})
        for k, v in data.items():
            if k in merged:
                continue
            if k in KNOWN_SECTIONS:
                continue
            merged.setdefault(k, v)

    return merged

