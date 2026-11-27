# 💼 Suivi de candidatures France Travail & Assistant IA

Application web Flask communautaire, gratuite et auto-hébergeable pour centraliser sa recherche d'emploi, consulter les offres multi-sources et générer des CV et lettres de motivation adaptés grâce à l'intelligence artificielle. Les fonctionnalités principales sont protégées par authentification et les données de chaque utilisateur restent privées par défaut.

🌐 **Instance communautaire en ligne :** [https://ftaccount.eu.pythonanywhere.com/](https://ftaccount.eu.pythonanywhere.com/)

---

## ✨ Fonctionnalités principales

- **Suivi complet des candidatures :** gestion CRUD des offres postulées (entreprise, intitulé, contact, e-mail, URL, dates clés, statuts actif/refusé, relances), pièces jointes/captures PDF (`static/images`), filtres multicritères et pagination.
- **Recherche d'offres multi-fournisseurs :** recherche manuelle ou guidée sur **France Travail**, **Adzuna** et **Jooble**, sauvegarde et rafraîchissement des recherches, déduplication lors de l'ajout en candidature et exports **CSV / XLSX / PDF**.
- **CV canonique unique :** stockage normalisé au format JSON Resume dans `static/uploads/users/<user_id>/cvs/cv.json` (dates `YYYY-MM-DD`). Compatible **GitConnected (JSON)**, **export PDF LinkedIn** et **CV PDF / DOCX / ODT** (extraction locale + conversion structurée par IA), avec conservation de l'original courant dans `cvs/originals/`.
- **Génération de CV et lettres de motivation par IA :** adaptation ciblée par offre, prévisualisation et édition, génération PDF du CV via ReportLab (`tools/cv_tools.py`) et de la lettre via LibreOffice/Word ou ReportLab (`tools/document_tools.py`). Compatible avec une IA locale (**Ollama**) ou des API distantes, avec gestion de clés personnelles chiffrées (**Fernet**) et repli sur la configuration IA du site.
- **Serveur MCP intégré (`jobs-tracker`) :** exposition des outils métier en **Stdio local** (`mcp_server.py`) et en **Streamable HTTP** (`POST /mcp`, protégé par jeton Bearer) pour permettre à un assistant IA (ex. Antigravity) d'ajouter des offres, stocker les lettres en base et générer les CV PDF depuis `cv.json` — voir [docs/MCP_SERVER.md](docs/MCP_SERVER.md).
- **Administration, quotas et conformité RGPD :**
  - cloisonnement strict des données par compte (partage des offres optionnel en opt-in) et rôle administrateur unique ;
  - activation des fournisseurs d'offres, suivi des quotas par période (25 req./mois Adzuna, 100 req./jour Jooble par défaut) et répartition par utilisateur dans **Admin → Fournisseurs d'offres** ;
  - suivi de l'usage IA mensuel (`AiUsage`, 20 appels/mois par défaut sur la clé du site) et traitement des demandes d'augmentation dans **Admin → IA et quotas** ;
  - gestion des sessions actives, suspension/réactivation de comptes avec motif, et suppression avec archivage privé (`instance/backups/deleted_users/`) ou purge définitive.

---

## 🚀 Installation et configuration locale

```bash
python3 -m pip install -r requirements.txt
cp config_template.py config.py
python3 flask_app.py
```

Variables principales à renseigner dans `config.py` ou l'environnement (selon les modules activés) :

- **Base & sécurité :** `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`
- **E-mails (SMTP) :** `SMTP_SERVER`, `SMTP_PORT`, `GMAIL_USER`, `GMAIL_APP_PWD`
- **Fournisseurs d'offres :** `FT_CLIENT_ID` / `FT_CLIENT_SECRET`, `ADZUNA_APP_ID` / `ADZUNA_APP_KEY`, `JOOBLE_API_KEY` / `JOOBLE_BASE_URL` (et seuils/quotas associés)
- **IA & chiffrement :** `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL`, `AI_CREDENTIALS_MASTER_KEY` (clé Fernet pour les clés personnelles)
- **Serveur MCP HTTP :** `MCP_API_TOKEN` (ou `JOBS_MCP_TOKEN`) et `MCP_USER_ID` (ou `JOBS_MCP_USER_ID`)

Les tables SQLite sont créées automatiquement au démarrage et lors des requêtes, avec migrations légères à la volée (aucun outil de migration externe requis). **Ne publiez jamais `config.py`, vos clés, mots de passe ou données utilisateurs dans Git ou les journaux.**

---

## 🧱 Architecture et routes principales

- `flask_app.py` : routes Flask, authentification, orchestration IA, fournisseurs d'offres et endpoint `/mcp`.
- `Model.py` : modèles SQLAlchemy (`User`, `Session`, `Job`, `FtSearch`, `AppSetting`, `UserAiCredential`, `AiUsage`, `AiQuotaRequest`).
- `Controller.py` : authentification (y compris mise à niveau des anciens hashs), uploads et e-mails.
- `tools/` : génération CV/LM et PDF (`cv_tools.py`, `document_tools.py`), intégration France Travail / Adzuna / Jooble, clés IA, quotas et logique MCP (`mcp_jobs.py`).
- `mcp_server.py` : point d'entrée Stdio du serveur MCP `jobs-tracker`.
- `templates/` & `static/uploads/users/<user_id>/` : interface Jinja2 et documents propres à chaque utilisateur.
- `instance/backups/deleted_users/` : archives privées des comptes supprimés.

**Routes utiles :** `/` (accueil) · `/suivi` (candidatures, CV/LM et compteur IA) · `/update_account/<id>` (coordonnées et CV) · `/france_travail` & `/france_travail/searches` (recherche et historique) · `/admin/job-offer-providers` · `/admin/ai-providers` · `/accounts` · `/mcp` · `/legal`.

---

## 🧪 Tests

```bash
python3 -m pytest -q
```

Tests ciblés utiles :

```bash
python3 -m pytest -q test/test_admin_roles.py
python3 -m pytest -q test/test_user_contact_info.py
python3 -m pytest -q test/test_mcp_jobs.py
```

---

## 📚 Documentation complémentaire

- [Fournisseurs IA et crédits](docs/AI_API_PROVIDERS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Serveur MCP](docs/MCP_SERVER.md)
- [Configuration Ollama](docs/OLLAMA.md)
- [Projet communautaire](docs/COMMUNITY_PROJECT.md)
- [Relais technique](docs/ANTIGRAVITY_HANDOFF.md)
