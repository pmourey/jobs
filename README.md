# 💼 Suivi de candidatures France Travail & Assistant IA

Application web communautaire, gratuite et auto-hébergeable permettant de centraliser sa recherche d'emploi, de consulter les offres France Travail et de générer des CV et lettres de motivation adaptés grâce à l'intelligence artificielle. Les fonctions
principales sont protégées par authentification ; les données de candidature
sont privées par défaut.

🌐 **Instance communautaire en ligne :** [https://pythonanywhere.com](https://pythonanywhere.com)

## ✨ Fonctionnalités principales
- **Tableau de bord de suivi :** centralisation des entreprises, contacts, dates clés, statuts et relances.
- **Intégration France Travail :** recherche d'offres d'emploi directement depuis l'interface.
- **Génération assistée par IA :** création et personnalisation de CV et lettres de motivation (compatible IA locale ou API distante).
- **Respect des données (RGPD) :** cloisonnement strict des comptes utilisateurs et partage optionnel.

## Architecture essentielle

- `flask_app.py` : routes Flask et orchestration de l'application.
- `Model.py` : modèles SQLAlchemy (`User`, `Job`, `Session`, recherches,
  configuration IA, quotas).
- `Controller.py` : authentification, uploads et e-mails.
- `tools/` : CV/LM, PDF, France Travail, fournisseurs IA et quotas.
- `templates/` : interface Jinja2.
- `static/uploads/users/<user_id>/` : données et documents propres à un
  utilisateur.
- `instance/backups/deleted_users/` : archives privées des comptes supprimés.

Le CV de référence est
`static/uploads/users/<user_id>/cvs/cv.json`. Les imports PDF, DOCX et ODT
extraient le texte localement puis utilisent l'IA configurée par le site pour
produire ce CV canonique. Un seul original courant est conservé dans
`cvs/originals/` et reste accessible depuis la gestion des CV, sous contrôle
d'authentification. Un nouvel import remplace simplement le CV canonique et
l'original courant.

Les sources compatibles sont GitConnected (JSON Resume), LinkedIn Export (PDF)
et les autres CV au format PDF, DOCX ou ODT. Les formats non structurés sont
convertis par l'IA configurée sur le site. Les dates des expériences,
formations, certifications et missions bénévoles sont normalisées en
`YYYY-MM-DD` ; lorsqu'un mois ou une année seulement est fourni, le premier jour
correspondant est utilisé.

## Installation locale

```bash
python3 -m pip install -r requirements.txt
cp config_template.py config.py
python3 flask_app.py
```

Configurer au minimum dans `config.py` ou l'environnement :

- `SECRET_KEY` et `SQLALCHEMY_DATABASE_URI` ;
- SMTP (`GMAIL_*`, `SMTP_SERVER`, `SMTP_PORT`) si les e-mails sont utilisés ;
- `FT_CLIENT_ID` et `FT_CLIENT_SECRET` pour France Travail en mode réel ;
- `JOOBLE_API_KEY` et `JOOBLE_BASE_URL=https://fr.jooble.org/api` pour activer Jooble ;
- `JOOBLE_DAILY_QUOTA` (100 par défaut) et
  `JOOBLE_QUOTA_THRESHOLD_PERCENT` (90 par défaut) pour contrôler les
  recherches Jooble des utilisateurs non administrateurs ;
- la configuration IA du site (`GITHUB_TOKEN`,
  `GITHUB_MODELS_BASE_URL`, `GITHUB_MODELS_MODEL`) si nécessaire ;
- `AI_CREDENTIALS_MASTER_KEY` pour chiffrer les clés IA personnelles.

`config.py`, les tokens, mots de passe et données utilisateurs ne doivent
jamais être ajoutés au dépôt ou aux journaux.

Les tables sont créées automatiquement. Les colonnes ajoutées au modèle
utilisateur sont complétées par une migration légère au démarrage/requête ;
aucune migration externe n'est actuellement requise.

## Fonctionnalités administrateur

- Une seule instance possède un seul profil Administrateur. Promouvoir un
  utilisateur transfère automatiquement le rôle et rétrograde les autres
  administrateurs.
- **IA et quotas** permet de configurer les fournisseurs, le quota mensuel et
  de traiter les demandes d'augmentation.
- Chaque utilisateur voit son quota IA de l'instance, ses appels utilisés et
  ses appels restants dans `/suivi`. Une clé personnelle utilise les quotas de
  son fournisseur et n'est pas comptabilisée dans le quota du site.
- Depuis **Comptes**, un administrateur peut suspendre/réactiver un compte
  avec un motif.
- La suppression peut archiver les données dans
  `instance/backups/deleted_users/` ou effectuer une purge définitive. Les
  reliquats de fichiers sont nettoyés même si le compte n'existe déjà plus en
  base.

## Quotas IA

Les appels effectués avec la configuration IA du site sont comptés dans
`AiUsage`, par utilisateur et par mois UTC. Le quota global est stocké dans
`AppSetting` sous `ai_site_monthly_quota`; un quota individuel peut être stocké
sous `ai_site_monthly_quota_user_<user_id>`. Le quota par défaut est de
20 appels mensuels par utilisateur.

À quota atteint, les routes IA retournent une erreur HTTP 429. Une demande
peut être envoyée depuis `/suivi` et est visible dans **Admin → IA et quotas**.

## Routes utiles

- `/` : accueil ;
- `/suivi` : candidatures, documents et compteur IA ;
- `/update_account/<id>` : profil, coordonnées et CV ;
- `/france_travail` : recherche d'offres ;
- `/admin/ai-providers` : fournisseurs IA, quotas et demandes ;
- `/accounts` : gestion administrateur des comptes ;
- `/legal` : informations publiques sur les données et la conservation.

## Tests

```bash
python3 -m pytest -q
```

Tests ciblés utiles :

```bash
python3 -m pytest -q test/test_admin_roles.py
python3 -m pytest -q test/test_user_contact_info.py
```

## Documentation complémentaire

- [Fournisseurs IA et crédits](docs/AI_API_PROVIDERS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Configuration Ollama](docs/OLLAMA.md)
- [Projet communautaire](docs/COMMUNITY_PROJECT.md)
- [Relais technique](docs/ANTIGRAVITY_HANDOFF.md)
