# AGENTS — Guide pour assistants IA (copilots)

But : permettre à un agent IA d'être immédiatement productif dans ce dépôt Flask.

1) Vue d'ensemble (big picture)
- Application monolithique Flask (entrée : `flask_app.py`) exposant routes UI et API pour CRUD candidatures, sessions, recherches France Travail et fonctionnalités IA (preview/generation CV/LM).
- Couche modèle : `Model.py` (SQLAlchemy) — User, Session, Job, FtSearch, AppSetting.
- Couche service/utilitaires : `Controller.py` (auth, uploads, envois mail) et `tools/` (CV/LM, PDF, FT API, envoi mail).
- Flow IA : routes `/preview_cv_data`, `/save_cv_pdf`, `/preview_lm_ai`, `/save_lm_text` appellent `tools.cv_tools` et utilisent `GITHUB_TOKEN` dans `config.py` comme source d'API IA.

2) Comment lancer / workflows courants
- Installer : `pip install -r requirements.txt` (voir `README.md`).
- Configuration locale : copier `config_template.py` → `config.py` puis renseigner `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`, `GMAIL_*` et optionnel `GITHUB_TOKEN`.
- Lancer serveur local : `python flask_app.py` (ouvre l'application, tables créées automatiquement via `db.create_all()` dans `@app.before_request`).
- Tests rapides disponibles dans `test/` ; ex : `python test/test_generate_cover_letter_pdf.py`.

3) Principales conventions et patterns spécifiques au projet
- Base monolithique : la logique métier est dans `flask_app.py` (routes) et `Controller.py` (fonctions partagées). Ne pas chercher un package service séparé.
- DB migration minimale : le projet applique des altérations légères à la volée (ex: ajout de colonne `ft_offer_id` dans `@app.before_request`). Les agents doivent éviter d'introduire migrations lourdes sans ajuster cette logique.
- Auth / rôles : rôles codés comme Enum `Role` dans `Model.py` (ADMIN=0, EDITOR=1, READER=2). Vérifier `is_admin`, `is_editor_or_admin` décorateurs dans `flask_app.py`.
- Sessions : Table `sessions` et logique de fermeture/ suppression en lot exposée via `/delete_sessions` (POST JSON {"ids": [...]}) — utile pour reproduire bugs liés aux sessions.
- Uploads : captures PDF validées dans `Controller.handle_file_upload` (taille max 2MB, header PDF check) et sauvegardées dans `static/images`.
- Hashs de mots de passe : prise en charge de formats legacy dans `Controller.check_password_and_upgrade` (sha256, md5) — les agents doivent conserver ce comportement lors de modifications d'auth.

4) Intégrations externes & points d'extension
- IA : `GITHUB_TOKEN`, `GITHUB_MODELS_BASE_URL`, `GITHUB_MODELS_MODEL` configurés dans `config.py`. Les appels IA se trouvent dans `tools/cv_tools.py` et `tools/document_tools.py`.
- SMTP : envoi d'e-mails via `tools.send_emails` et wrappers dans `Controller.py` (utilise `GMAIL_USER`, `GMAIL_APP_PWD`, `SMTP_SERVER`, `SMTP_PORT`).
- France Travail API : implémenté dans `tools/france_travail.py` et orchestré depuis `flask_app.py` (endpoints /france_travail). Besoin de `FT_CLIENT_ID` / `FT_CLIENT_SECRET` dans `config.py` pour le mode réel.

5) Patterns de code et anti-odeurs à noter
- Beaucoup de logique côté route (flask_app) — pour refactors, extraire en services en gardant l'API interne (Controller + tools).
- Utilisation explicite de fichiers statiques pour artefacts produits (static/uploads cv_{id}.pdf, static/images capture_{id}.pdf). Tests et features s'appuient sur ces chemins.
- Gestion des erreurs IA : les routes ont des fallbacks locaux si `GITHUB_TOKEN` absent — conserver ces fallbacks pour tests hors réseau.
- Utilisation de `db.create_all()` avant chaque requête : la base SQLite est créée automatiquement. Les agents doivent tenir compte de ce comportement lors d'écriture de scripts de migration ou de tests d'intégration.

6) Fichiers clés à consulter (exemples concret)
- `flask_app.py` : orchestration, routes, décorateurs d'autorisation, logique France Travail, génération PDF endpoints.
- `Model.py` : schéma SQLAlchemy, validation email, méthodes utilitaires (offers getter/setter pour FtSearch).
- `Controller.py` : upload validation, envois d'e-mails, vérification/upgrade des mots de passe legacy.
- `config_template.py` / `config.py` : variables d'environnement et secrets attendus (GITHUB_TOKEN, GMAIL_APP_PWD, FT_CLIENT_ID, etc.).
- `tools/` (notamment `cv_tools.py`, `document_tools.py`, `send_emails.py`, `france_travail.py`) : implémentations IA, PDF et intégrations externes.

7) Conseils pratiques pour modifications par un agent IA
- Ne pas supprimer la logique de compatibilité des hash de mot de passe sans migrer les comptes existants (vérifier `LEGACY_HASH_METHODS`).
- Pour changer la DB : tester localement en créant `instance/jobs.sqlite3` ou en pointant `SQLALCHEMY_DATABASE_URI` vers une instance test ; la création automatique facilite les tests mais cache les migrations.
- Quand vous touchez aux endpoints IA : fournir un fallback quand `GITHUB_TOKEN` est vide (cf. `preview_cv_data` / `_fallback`).
- Respecter chemins statiques existants (`static/uploads`, `static/images`) — les noms de fichiers suivant la convention (`cv_{id}.pdf`, `capture_{id}.pdf`).

8) Commandes utiles (résumé)
- Installer dépendances : python -m pip install --upgrade pip && pip install -r requirements.txt
- Copier config : cp config_template.py config.py && éditer `config.py` (GMAIL/GITHUB/DB)
- Lancer serveur : python flask_app.py
- Lancer un test unitaire : python test/test_generate_cover_letter_pdf.py

9) Checklist rapide pour un agent qui propose un PR
- Expliquer impact sur `config.py` (nouveaux variables) si ajout d'intégration.
- Ajouter tests unitaires dans `test/` et utiliser les fallbacks pour tests offline.
- Ne pas modifier directement `db.create_all()` behavior sans justification ; documenter les migrations nécessaires.

---
Références : `README.md`, `flask_app.py`, `Model.py`, `Controller.py`, `config_template.py`, `tools/`.

