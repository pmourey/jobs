# Suivi de Candidatures

Application Flask de suivi de candidatures avec authentification, gestion des rôles, génération de documents (LM/CV) et assistants IA pour personnaliser les candidatures.

## Démo

[https://pmourey.pythonanywhere.com/](https://pmourey.pythonanywhere.com/)

## Fonctionnalités principales

- Gestion des candidatures : création, modification, suppression, archivage (actif/clos), suivi des dates et du texte de lettre.
- Authentification complète : inscription, validation e-mail, connexion/déconnexion, changement et récupération de mot de passe.
- Gestion des rôles : Administrateur, Éditeur, Lecteur avec restrictions d'accès par route.
- Administration des comptes et sessions : sessions actives, sessions fermées, fermeture/suppression unitaire ou en lot.
- Génération de lettre de motivation PDF côté serveur via ReportLab (sans Word ni LibreOffice en production).
- Personnalisation IA du CV : aperçu des suggestions, sélection fine des sections, génération et sauvegarde d'un CV PDF.
- Génération IA de lettre de motivation : prévisualisation, ajustement via prompt complémentaire, sauvegarde dans la candidature.
- Upload de capture de candidature (PDF) avec validation côté serveur.

## Nouveautés récentes

- Ajout de l'endpoint de génération LM PDF : /generate_cover_letter_pdf/<id>
- Ajout du flux CV IA :
  - /preview_cv_data/<id> (aperçu JSON)
  - /save_cv_pdf/<id> (génération + sauvegarde dans static/uploads)
  - /generate_cv_pdf/<id> (téléchargement du CV sauvegardé ou fallback dynamique)
- Ajout du flux LM IA :
  - /preview_lm_ai/<id> (génération de texte)
  - /save_lm_text/<id> (persistance en base)
- Ajout de la suppression/fermeture de sessions en lot : /delete_sessions (POST JSON)
- Messages de validation formulaire renforcés sur /new/ (champs requis, e-mail invalide, conservation des valeurs saisies)

## Prérequis

- Python 3.10+
- Pip
- Compte Gmail + mot de passe d'application (si envoi d'e-mails activé)
- Optionnel : token GitHub Models pour les fonctionnalités IA

LibreOffice est optionnel et utile surtout pour des conversions locales de templates legacy .dot. Le rendu PDF principal est géré en Python.

## Installation

1. Cloner le dépôt

```bash
git clone <repository-url>
cd jobs
```

2. Installer les dépendances

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3. Créer la configuration locale

```bash
cp config_template.py config.py
```

4. Renseigner les variables dans config.py

- SMTP_SERVER, SMTP_PORT, GMAIL_USER, GMAIL_APP_PWD
- SECRET_KEY
- SQLALCHEMY_DATABASE_URI
- GITHUB_TOKEN (optionnel, recommandé pour IA)
- GITHUB_MODELS_BASE_URL, GITHUB_MODELS_MODEL

## Données et fichiers attendus

- static/cv.json : base CV utilisée pour la personnalisation IA.
- static/Cover_letter.dot ou static/Cover_letter.dotx : template de lettre.
- static/uploads/ : PDFs générés (créé automatiquement si absent).
- static/images/ : captures de candidature et ressources associées.

## Lancer l'application

```bash
python flask_app.py
```

Puis ouvrir le navigateur sur l'URL Flask affichée en console.

## Endpoints utiles

- /suivi : liste des candidatures
- /new/ : création d'une candidature
- /update/<id> : édition d'une candidature
- /toggle_expired/<id> : bascule actif/clos
- /generate_cover_letter_pdf/<id> : téléchargement LM PDF
- /preview_cv_data/<id> : aperçu des recommandations IA CV (POST)
- /save_cv_pdf/<id> : génération + sauvegarde CV PDF (POST)
- /generate_cv_pdf/<id> : téléchargement CV PDF
- /preview_lm_ai/<id> : génération IA LM (POST)
- /save_lm_text/<id> : sauvegarde texte LM (POST)
- /sessions, /closed_sessions : suivi des sessions
- /delete_sessions : fermeture/suppression de sessions en lot (POST JSON)

## Tests

Des scripts de test sont disponibles dans test/, notamment :

- test/test_generate_cover_letter_pdf.py
- test/test_delete_sessions.py
- test/test_new_route.py
- test/test_empty_form.py

Exemple :

```bash
python test/test_generate_cover_letter_pdf.py
```

## Sécurité et validation

- Contrôles d'accès par rôle sur les routes sensibles.
- Validation des entrées formulaire (obligatoires, format e-mail).
- Gestion de session côté serveur avec invalidation automatique si session fermée par admin.
- Gestion des erreurs/fallback en cas d'indisponibilité IA (aperçus et génération dégradés).

## Structure du projet

- flask_app.py : routes Flask et orchestration métier.
- Model.py : modèles SQLAlchemy.
- Controller.py : services applicatifs (auth, e-mail, upload).
- tools/document_tools.py : génération et utilitaires LM/PDF.
- tools/cv_tools.py : IA CV/LM et génération CV PDF.
- templates/ : vues Jinja2.
- static/ : assets, templates documents, uploads.

## Contact

Pour toute question ou incident, contacter l'auteur du projet.

