# Suivi de candidatures

Application web Flask pour organiser une recherche d'emploi, suivre ses candidatures et préparer des documents personnalisés. Une page publique présente le service avant connexion ; les fonctionnalités de gestion sont accessibles après création et validation d'un compte.

## Pour les utilisateurs

### Ce que le service permet

- **Centraliser ses candidatures** : entreprise, poste, contact, dates, statut, relances et notes.
- **Retrouver ses documents** : CV source, CV générés, lettres de motivation et captures PDF.
- **Préparer chaque candidature** : génération d'une lettre PDF et personnalisation du CV à partir du profil et de l'offre.
- **Utiliser une assistance IA** : suggestions de contenu, aperçu et génération de CV/lettre ; les résultats doivent toujours être relus avant envoi.
- **Rechercher des offres** : France Travail et, selon la configuration, des job boards compatibles.
- **Garder le contrôle** : les candidatures sont privées par défaut ; le partage avec d'autres utilisateurs est une option explicite.
- **Gérer son compte** : validation e-mail, changement/récupération du mot de passe, coordonnées, CV et photo.

La page d'accueil publique est disponible sur `/`. Les informations de confidentialité et les conditions d'utilisation sont accessibles sur `/legal`.

## Démonstration

[https://pmourey.pythonanywhere.com/](https://pmourey.pythonanywhere.com/)

## Démarrage local

### Prérequis

- Python 3.10 ou plus récent ;
- pip ;
- un compte Gmail et un mot de passe d'application si les e-mails sont activés ;
- des identifiants France Travail pour la recherche d'offres en mode réel ;
- un fournisseur IA local ou distant si l'assistance IA est activée.

### Installation

```bash
git clone <repository-url>
cd jobs
python -m pip install --upgrade pip
pip install -r requirements.txt
cp config_template.py config.py
```

Renseignez ensuite `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`, les paramètres SMTP et, si nécessaire, les identifiants France Travail et IA. Ne commitez jamais `config.py`, les mots de passe, les tokens ou les données utilisateurs.

```bash
python flask_app.py
```

Puis ouvrez l'URL affichée par Flask. Les tables SQLite sont créées automatiquement au démarrage des requêtes selon la configuration actuelle du projet.

## Configuration et documentation technique

Les détails opérationnels sont volontairement séparés de cette présentation :

- [Configuration IA locale avec Ollama](docs/OLLAMA.md)
- [Architecture technique et flux de données](docs/ARCHITECTURE.md)
- [Configuration de référence](config_template.py)

Le fonctionnement d'Ollama est optionnel. Sans service IA disponible, les parcours CV/LM disposent de replis locaux lorsque la fonctionnalité le permet.

## Principales routes authentifiées

- `/suivi` : candidatures de l'utilisateur ;
- `/new/` et `/update/<id>` : création et modification ;
- `/generate_cover_letter_pdf/<id>` : lettre de motivation PDF ;
- `/preview_cv_data/<id>`, `/save_cv_pdf/<id>`, `/generate_cv_pdf/<id>` : CV personnalisé ;
- `/preview_lm_ai/<id>` et `/save_lm_text/<id>` : assistance IA pour la lettre ;
- `/france_travail` : recherches et résultats d'offres ;
- `/update_account/<id>` : coordonnées, CV source et préférences du compte.

## Données personnelles, sécurité et usage commercial

Le service peut traiter des coordonnées, CV, candidatures, documents, données de session et recherches d'offres. Les mesures prévues dans l'application comprennent notamment l'authentification, les mots de passe hachés, les contrôles d'accès par rôle, la séparation des répertoires utilisateurs, la validation des uploads et le partage des offres désactivé par défaut.

Avant une ouverture commerciale, l'exploitant doit compléter et valider juridiquement les mentions accessibles sur [`/legal`](templates/legal.html), notamment l'identité du responsable de traitement, les bases légales, les durées de conservation, les sous-traitants, les transferts hors UE, les procédures d'exercice des droits et les coordonnées de contact RGPD. Le contenu fourni est une base d'information et ne constitue pas un avis juridique.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Les tests ciblés utiles comprennent `test/test_user_contact_info.py`, `test/test_generate_cover_letter_pdf.py`, `test/test_new_route.py` et `test/test_delete_sessions.py`.

## Structure du projet

- `flask_app.py` : routes et orchestration ;
- `Model.py` : modèles SQLAlchemy ;
- `Controller.py` : authentification, uploads et e-mails ;
- `tools/cv_tools.py` : CV, coordonnées et assistance IA ;
- `tools/document_tools.py` : lettres et PDF ;
- `tools/france_travail.py` : API France Travail ;
- `templates/` : interface Jinja2 ;
- `static/` : ressources, modèles et fichiers générés.

## Copyright

Copyright © 2024-2026 Philippe Mourey. Le code est publié selon la licence présente dans le dépôt lorsqu'elle est définie. Les contenus, modèles de documents, marques et données utilisateurs peuvent être soumis à des droits distincts.
